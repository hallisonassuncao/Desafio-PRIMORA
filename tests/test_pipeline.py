from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from etl.cep_client import ConsultaCep
from etl.pipeline import executar, resumir, tratar_cliente

CSV = Path(__file__).parent.parent / "data" / "clientes_distribuidora_vetor.csv"


class CepFalso:
    """Substitui o ClienteCep: devolve respostas fixas, sem rede e sem cache em disco."""

    def __init__(self, tabela):
        self.tabela = tabela
        self.chamadas = []
        self.stats = {"cache": 0, "api": 0, "falhas": 0}

    def consultar(self, cep):
        self.chamadas.append(cep)
        self.stats["api"] += 1
        return self.tabela.get(cep)


def linha(**kw):
    base = {"id_cliente": "T1", "razao_social": "  Loja   Teste ", "cnpj": "11222333000181",
            "telefone": "61970855700", "email": "a@b.com", "bairro_informado": "aguas claras",
            "cep": "", "cidade": "Brasília", "uf": "DF", "data_cadastro": "2022-01-31",
            "vendedor_responsavel": "Fulano"}
    base.update(kw)
    return base


def test_tratar_cliente_sem_api(dicionario):
    reg, aud = tratar_cliente(linha(), dicionario)
    assert reg["razao_social"] == "Loja Teste"
    assert reg["bairro"] == "Águas Claras" and reg["bairro_fonte"] == "informado"
    assert reg["telefone"] == "+5561970855700" and reg["cnpj"] == "11.222.333/0001-81"
    campos = {a["campo"] for a in aud}
    assert {"razao_social", "telefone", "bairro", "cep"} <= campos
    bairro = next(a for a in aud if a["campo"] == "bairro")
    assert bairro["valor_original"] == "aguas claras" and bairro["valor_tratado"] == "Águas Claras"


def test_cep_divergente_prevalece_a_api_e_audita(dicionario):
    api = CepFalso({"72140-010": ConsultaCep("72140-010", "Taguatinga Sul", "Brasília", "DF", "viacep")})
    reg, aud = tratar_cliente(linha(bairro_informado="Sul (Águas Claras)", cep="72140-010"),
                              dicionario, api)
    assert (reg["bairro"], reg["subdivisao"]) == ("Taguatinga", "Sul")
    assert reg["divergencia_cep_bairro"] is True
    b = next(a for a in aud if a["campo"] == "bairro")
    assert b["fonte"] == "api_cep" and "divergencia_api_prevalece" in b["criterio"]
    assert "viacep" in b["criterio"]


def test_cep_invalido_nao_chama_api(dicionario):
    api = CepFalso({})
    reg, _ = tratar_cliente(linha(cep="00000-000"), dicionario, api)
    assert api.chamadas == [] and reg["cep_status"] == "invalido" and reg["cep"] is None


def test_cep_de_outra_uf_e_ignorado(dicionario):
    api = CepFalso({"01001-000": ConsultaCep("01001-000", "Sé", "São Paulo", "SP", "viacep")})
    reg, aud = tratar_cliente(linha(cep="01001-000"), dicionario, api)
    assert reg["bairro"] == "Águas Claras" and reg["bairro_fonte"] == "informado"
    assert any(a["criterio"] == "cep_de_outra_uf_ignorado" and a["revisao_manual"] for a in aud)


@pytest.fixture
def engine():
    return create_engine("sqlite://")


def test_pipeline_ponta_a_ponta_com_csv_real(engine, dicionario):
    api = CepFalso({"72140-010": ConsultaCep("72140-010", "Taguatinga Sul", "Brasília", "DF", "viacep")})
    linhas, clientes, auditoria = executar(CSV, engine, api)
    r = resumir(linhas, clientes, auditoria, api)

    assert r["clientes"] == 47
    assert r["bairros_distintos_depois"] == 4          # Águas Claras, Taguatinga, Vicente Pires, Guará
    assert r["grafias_distintas_bairro_antes"] == 26   # 25 grafias + vazio
    assert r["clientes_sem_bairro"] == 1               # CLI0047
    assert r["divergencias_cep_bairro"] == 1           # CLI0002 (Sul (Águas Claras) x CEP de Taguatinga)
    assert r["cnpj_dv_invalido"] == 47                 # base sintética: nenhum DV válido, nenhum descartado

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM clientes_tratados")).scalar() == 47
        assert conn.execute(text("SELECT COUNT(*) FROM auditoria_tratamento")).scalar() == len(auditoria)
        grupos = conn.execute(text(
            "SELECT bairro, COUNT(*) FROM clientes_tratados WHERE bairro IS NOT NULL "
            "GROUP BY bairro")).fetchall()
        assert len(grupos) == 4
        cli2 = conn.execute(text(
            "SELECT bairro, subdivisao, divergencia_cep_bairro FROM clientes_tratados "
            "WHERE id_cliente='CLI0002'")).one()
        assert cli2[0] == "Taguatinga" and cli2[1] == "Sul" and cli2[2] == 1


def test_carga_e_idempotente(engine):
    executar(CSV, engine)
    executar(CSV, engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM clientes_tratados")).scalar() == 47
