from etl.normalizers import ResultadoBairro, normalizar_bairro
from etl.resolucao import resolver_bairro


def inf(dicionario, texto):
    return normalizar_bairro(texto, dicionario)


def test_sem_api_usa_informado(dicionario):
    r = resolver_bairro(inf(dicionario, "Sul (Aguas Claras)"), None)
    assert (r.bairro, r.subdivisao, r.fonte) == ("Águas Claras", "Sul", "informado")
    assert not r.divergencia and not r.revisao_manual


def test_sem_api_e_sem_informado(dicionario):
    r = resolver_bairro(inf(dicionario, ""), None)
    assert r.bairro is None and r.fonte == "nenhuma" and not r.revisao_manual


def test_informado_nao_mapeado_sem_api_pede_revisao(dicionario):
    r = resolver_bairro(inf(dicionario, "Ceilândia"), None)
    assert r.bairro is None and r.revisao_manual


def test_concordam_mantem_subdivisao_informada(dicionario):
    api = normalizar_bairro("Águas Claras", dicionario)
    r = resolver_bairro(inf(dicionario, "Norte (Águas Claras)"), api)
    assert (r.bairro, r.subdivisao, r.criterio) == ("Águas Claras", "Norte", "concordam")
    assert not r.divergencia


def test_concordam_herda_subdivisao_da_api(dicionario):
    api = normalizar_bairro("Taguatinga Sul", dicionario)
    r = resolver_bairro(inf(dicionario, "Taguatinga"), api)
    assert (r.bairro, r.subdivisao) == ("Taguatinga", "Sul")


def test_divergencia_api_prevalece(dicionario):
    api = normalizar_bairro("Taguatinga Sul", dicionario)
    r = resolver_bairro(inf(dicionario, "Sul (Águas Claras)"), api)
    assert (r.bairro, r.subdivisao, r.fonte) == ("Taguatinga", "Sul", "api_cep")
    assert r.divergencia and r.criterio == "divergencia_api_prevalece"


def test_informado_vazio_usa_api(dicionario):
    api = normalizar_bairro("Guará II", dicionario)
    r = resolver_bairro(inf(dicionario, ""), api)
    assert (r.bairro, r.subdivisao, r.fonte) == ("Guará", "II", "api_cep")
    assert not r.divergencia


def test_api_fora_do_dicionario_mantem_informado_e_pede_revisao(dicionario):
    api = normalizar_bairro("Setor Industrial", dicionario)
    r = resolver_bairro(inf(dicionario, "Taguatinga"), api)
    assert r.bairro == "Taguatinga" and r.fonte == "informado" and r.revisao_manual


def test_api_sem_bairro_cai_no_informado(dicionario):
    r = resolver_bairro(inf(dicionario, "Vte Pires"), ResultadoBairro(None, None, "vazio"))
    assert r.bairro == "Vicente Pires" and r.fonte == "informado" and not r.revisao_manual
