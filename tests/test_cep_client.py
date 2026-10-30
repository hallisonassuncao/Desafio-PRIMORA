import sqlite3

import requests

from etl.cep_client import ClienteCep
from tests.conftest import RespostaFalsa, SessaoFalsa

VIACEP_OK = {"cep": "71926-750", "bairro": "Águas Claras", "localidade": "Brasília", "uf": "DF"}
BRASILAPI_OK = {"cep": "71926750", "neighborhood": "Águas Claras", "city": "Brasília", "state": "DF"}


def cliente(tmp_path, respostas):
    sessao = SessaoFalsa(respostas)
    return ClienteCep(str(tmp_path / "c.sqlite"), sessao=sessao), sessao


def test_viacep_ok_e_cache_evita_segunda_chamada(tmp_path):
    c, sessao = cliente(tmp_path, {"viacep": RespostaFalsa(200, VIACEP_OK)})
    r1 = c.consultar("71926-750")
    r2 = c.consultar("71926750")
    assert r1.bairro == "Águas Claras" and r1.fonte == "viacep" and r1.cep == "71926-750"
    assert r2 == r1
    assert len(sessao.chamadas) == 1
    assert c.stats == {"cache": 1, "api": 1, "falhas": 0}


def test_cache_persiste_entre_instancias(tmp_path):
    c1, _ = cliente(tmp_path, {"viacep": RespostaFalsa(200, VIACEP_OK)})
    c1.consultar("71926-750")
    c1.fechar()
    c2, sessao2 = cliente(tmp_path, {})  # qualquer chamada de rede quebraria o teste
    assert c2.consultar("71926-750").bairro == "Águas Claras"
    assert sessao2.chamadas == []


def test_fallback_para_brasilapi_quando_viacep_falha(tmp_path):
    c, sessao = cliente(tmp_path, {
        "viacep": RespostaFalsa(503),
        "brasilapi": RespostaFalsa(200, BRASILAPI_OK),
    })
    r = c.consultar("71926-750")
    assert r.fonte == "brasilapi" and r.bairro == "Águas Claras"
    assert c.stats["falhas"] == 1 and len(sessao.chamadas) == 2


def test_timeout_nos_dois_provedores_nao_cacheia(tmp_path):
    c, sessao = cliente(tmp_path, {
        "viacep": requests.Timeout("lento"),
        "brasilapi": requests.ConnectionError("fora do ar"),
    })
    assert c.consultar("71926-750") is None
    assert c.stats["falhas"] == 2
    c.consultar("71926-750")  # sem cache: tenta de novo
    assert len(sessao.chamadas) == 4


def test_cep_inexistente_e_cacheado_como_negativo(tmp_path):
    c, sessao = cliente(tmp_path, {
        "viacep": RespostaFalsa(200, {"erro": True}),
        "brasilapi": RespostaFalsa(404),
    })
    assert c.consultar("99999-999") is None
    assert c.consultar("99999-999") is None
    assert len(sessao.chamadas) == 2  # 2 provedores na 1ª vez, 0 na 2ª
    assert c.stats["cache"] == 1


def test_inexistente_no_viacep_mas_falha_no_brasilapi_nao_cacheia(tmp_path):
    c, sessao = cliente(tmp_path, {
        "viacep": RespostaFalsa(200, {"erro": True}),
        "brasilapi": RespostaFalsa(500),
    })
    assert c.consultar("99999-999") is None
    c.consultar("99999-999")
    assert len(sessao.chamadas) == 4


def test_bairro_vazio_no_viacep_tenta_brasilapi(tmp_path):
    vazio = {**VIACEP_OK, "bairro": ""}
    c, _ = cliente(tmp_path, {
        "viacep": RespostaFalsa(200, vazio),
        "brasilapi": RespostaFalsa(200, BRASILAPI_OK),
    })
    assert c.consultar("71926-750").fonte == "brasilapi"


def test_json_invalido_conta_como_falha(tmp_path):
    c, _ = cliente(tmp_path, {
        "viacep": RespostaFalsa(200, erro_json=True),
        "brasilapi": RespostaFalsa(200, BRASILAPI_OK),
    })
    assert c.consultar("71926-750").fonte == "brasilapi"
    assert c.stats["falhas"] == 1


def test_arquivo_de_cache_tem_uma_linha_por_cep(tmp_path):
    c, _ = cliente(tmp_path, {"viacep": RespostaFalsa(200, VIACEP_OK)})
    c.consultar("71926-750")
    n = sqlite3.connect(tmp_path / "c.sqlite").execute("SELECT COUNT(*) FROM cep_cache").fetchone()[0]
    assert n == 1
