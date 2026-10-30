"""Extração, transformação e carga (ETL) da base de clientes da Distribuidora Vetor."""
import csv
import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, Date, DateTime, Integer, MetaData, String, Table,
                        Text, delete, insert)

from .normalizers import (ResultadoBairro, carregar_dicionario, normalizar_bairro,
                          normalizar_cep, normalizar_cnpj, normalizar_data, normalizar_email,
                          normalizar_telefone)
from .resolucao import resolver_bairro

metadata = MetaData()

clientes_tratados = Table(
    "clientes_tratados", metadata,
    Column("id_cliente", String(20), primary_key=True),
    Column("razao_social", String(200)),
    Column("cnpj", String(18)),
    Column("cnpj_dv_valido", Boolean),
    Column("telefone", String(15)),
    Column("telefone_tipo", String(10)),
    Column("email", String(150)),
    Column("email_valido", Boolean),
    Column("cep", String(9)),
    Column("cep_status", String(30)),
    Column("bairro_informado", String(100)),
    Column("bairro", String(100)),
    Column("subdivisao", String(30)),
    Column("bairro_fonte", String(30)),
    Column("divergencia_cep_bairro", Boolean),
    Column("revisao_manual", Boolean),
    Column("cidade", String(80)),
    Column("uf", String(2)),
    Column("data_cadastro", Date),
    Column("data_ambigua", Boolean),
    Column("vendedor_responsavel", String(100)),
)

auditoria_tratamento = Table(
    "auditoria_tratamento", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("id_cliente", String(20), index=True),
    Column("campo", String(30)),
    Column("valor_original", Text),
    Column("valor_tratado", Text),
    Column("criterio", Text),
    Column("fonte", String(30)),
    Column("revisao_manual", Boolean),
    Column("executado_em", DateTime(timezone=True)),
)


# ---------------------------------------------------------------- extração
def extrair(caminho_csv):
    with open(caminho_csv, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


# ----------------------------------------------------------- transformação
def _nulo(v):
    v = (v or "").strip()
    return v or None


def tratar_cliente(linha, dicionario, cliente_cep=None):
    """-> (registro tratado, lista de entradas de auditoria)."""
    auditoria = []

    def reg(campo, original, tratado, criterio, fonte="regra", revisao=False):
        o = (original or "").strip()
        t = "" if tratado is None else str(tratado)
        if o != t or criterio != "ok":
            auditoria.append({
                "id_cliente": linha["id_cliente"], "campo": campo,
                "valor_original": o or None, "valor_tratado": t or None,
                "criterio": criterio, "fonte": fonte, "revisao_manual": revisao,
            })

    razao = re.sub(r"\s+", " ", linha["razao_social"] or "").strip()
    reg("razao_social", linha["razao_social"], razao, "ok")

    cnpj, cnpj_ok, c_cnpj = normalizar_cnpj(linha["cnpj"])
    reg("cnpj", linha["cnpj"], cnpj, c_cnpj)

    tel, tel_tipo, c_tel = normalizar_telefone(linha["telefone"])
    reg("telefone", linha["telefone"], tel, c_tel if c_tel != "ok" else "ok_e164")

    email, email_ok, c_email = normalizar_email(linha["email"])
    reg("email", linha["email"], email, c_email)

    data, fmt_data, ambigua = normalizar_data(linha["data_cadastro"])
    c_data = f"formato={fmt_data}" + ("; ambigua_assumido_dd/mm" if ambigua else "")
    reg("data_cadastro", linha["data_cadastro"], data.isoformat() if data else None,
        "ok" if fmt_data == "iso" else c_data)

    cep, cep_status = normalizar_cep(linha["cep"])
    reg("cep", linha["cep"], cep, "ok" if cep_status == "ok" else f"cep_{cep_status}")

    # --- bairro: informado x API de CEP
    informado = normalizar_bairro(linha["bairro_informado"], dicionario)
    api = None
    consulta = None
    if cep and cliente_cep is not None:
        consulta = cliente_cep.consultar(cep)
        if consulta and consulta.uf and consulta.uf.upper() != (linha["uf"] or "").upper():
            # CEP de outra UF: não confiamos no bairro devolvido
            reg("cep", cep, cep, "cep_de_outra_uf_ignorado", "api_cep", True)
            consulta = None
        if consulta and consulta.bairro:
            api = normalizar_bairro(consulta.bairro, dicionario)
        elif consulta:
            api = ResultadoBairro(None, None, "vazio")
    res = resolver_bairro(informado, api)
    final = res.bairro + (f" / {res.subdivisao}" if res.subdivisao else "") if res.bairro else None
    detalhe = res.criterio
    if consulta and consulta.bairro:
        detalhe += f" (api={consulta.fonte}: '{consulta.bairro}')"
    reg("bairro", linha["bairro_informado"], final, detalhe, res.fonte, res.revisao_manual)

    registro = {
        "id_cliente": linha["id_cliente"], "razao_social": razao,
        "cnpj": cnpj, "cnpj_dv_valido": cnpj_ok,
        "telefone": tel, "telefone_tipo": tel_tipo,
        "email": email, "email_valido": email_ok,
        "cep": cep, "cep_status": cep_status,
        "bairro_informado": _nulo(linha["bairro_informado"]),
        "bairro": res.bairro, "subdivisao": res.subdivisao, "bairro_fonte": res.fonte,
        "divergencia_cep_bairro": res.divergencia, "revisao_manual": res.revisao_manual,
        "cidade": _nulo(linha["cidade"]), "uf": _nulo(linha["uf"]),
        "data_cadastro": data, "data_ambigua": ambigua,
        "vendedor_responsavel": _nulo(linha["vendedor_responsavel"]),
    }
    return registro, auditoria


def transformar(linhas, dicionario, cliente_cep=None):
    clientes, auditoria = [], []
    for linha in linhas:
        c, a = tratar_cliente(linha, dicionario, cliente_cep)
        clientes.append(c)
        auditoria.extend(a)
    return clientes, auditoria


# ------------------------------------------------------------------- carga
def carregar(engine, clientes, auditoria):
    """Recarga completa e atômica (idempotente): reexecutar não duplica linhas."""
    metadata.create_all(engine)
    agora = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(delete(auditoria_tratamento))
        conn.execute(delete(clientes_tratados))
        if clientes:
            conn.execute(insert(clientes_tratados), clientes)
        if auditoria:
            conn.execute(insert(auditoria_tratamento),
                         [{**a, "executado_em": agora} for a in auditoria])


def resumir(linhas, clientes, auditoria, cliente_cep=None):
    return {
        "clientes": len(clientes),
        "grafias_distintas_bairro_antes": len({(l["bairro_informado"] or "").strip() for l in linhas}),
        "bairros_distintos_depois": len({c["bairro"] for c in clientes if c["bairro"]}),
        "clientes_sem_bairro": sum(1 for c in clientes if not c["bairro"]),
        "cep_status": dict(Counter(c["cep_status"] for c in clientes)),
        "bairro_fonte": dict(Counter(c["bairro_fonte"] for c in clientes)),
        "divergencias_cep_bairro": sum(1 for c in clientes if c["divergencia_cep_bairro"]),
        "revisao_manual": sum(1 for c in clientes if c["revisao_manual"]),
        "datas_ambiguas": sum(1 for c in clientes if c["data_ambigua"]),
        "cnpj_dv_invalido": sum(1 for c in clientes if c["cnpj_dv_valido"] is False),
        "telefones_invalidos": sum(1 for c in clientes if c["telefone"] is None),
        "emails_invalidos": sum(1 for c in clientes if c["email_valido"] is False),
        "linhas_de_auditoria": len(auditoria),
        "cache_cep": cliente_cep.stats if cliente_cep else None,
    }


def executar(caminho_csv, engine, cliente_cep=None, caminho_dicionario=None):
    linhas = extrair(caminho_csv)
    dicionario = carregar_dicionario(caminho_dicionario)
    clientes, auditoria = transformar(linhas, dicionario, cliente_cep)
    carregar(engine, clientes, auditoria)
    return linhas, clientes, auditoria
