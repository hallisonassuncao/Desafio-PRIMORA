from datetime import date

import pytest

from etl.normalizers import (chave_texto, cnpj_dv_valido, normalizar_bairro, normalizar_cep,
                             normalizar_cnpj, normalizar_data, normalizar_email,
                             normalizar_telefone)


# ------------------------------------------------------------------ bairro
@pytest.mark.parametrize("entrada,bairro,sub", [
    ("Águas Claras", "Águas Claras", None),
    ("Aguas claras", "Águas Claras", None),
    ("AGUAS CLARAS", "Águas Claras", None),
    ("Águas Claras/DF", "Águas Claras", None),
    ("Aguas Claras - DF", "Águas Claras", None),
    ("Sul (Águas Claras)", "Águas Claras", "Sul"),
    ("Norte (Aguas Claras)", "Águas Claras", "Norte"),
    ("Águas Claras Norte", "Águas Claras", "Norte"),
    ("taguatinga sul", "Taguatinga", "Sul"),
    ("Taguatinga/DF", "Taguatinga", None),
    ("Vte Pires", "Vicente Pires", None),
    ("V. Pires", "Vicente Pires", None),
    ("VICENTE PIRES", "Vicente Pires", None),
    ("guara - df", "Guará", None),
    ("Guará II", "Guará", "II"),
])
def test_bairro_variantes(dicionario, entrada, bairro, sub):
    r = normalizar_bairro(entrada, dicionario)
    assert (r.bairro, r.subdivisao) == (bairro, sub)
    assert r.criterio == "dicionario" and not r.revisao_manual


def test_bairro_vazio(dicionario):
    r = normalizar_bairro("", dicionario)
    assert r.bairro is None and r.criterio == "vazio" and not r.revisao_manual


def test_bairro_nao_mapeado_pede_revisao(dicionario):
    r = normalizar_bairro("Ceilândia", dicionario)
    assert r.bairro is None and r.criterio == "nao_mapeado" and r.revisao_manual


def test_bairro_erro_de_digitacao_vira_fuzzy_com_revisao(dicionario):
    r = normalizar_bairro("Taguatigna", dicionario)
    assert r.bairro == "Taguatinga" and r.criterio == "fuzzy" and r.revisao_manual


def test_chave_texto():
    assert chave_texto("  Sul (Águas  Claras) - DF ") == "sul aguas claras"


# --------------------------------------------------------------------- cep
@pytest.mark.parametrize("entrada,esperado", [
    ("71926-750", ("71926-750", "ok")),
    ("71926750", ("71926-750", "ok")),
    ("", (None, "ausente")),
    ("00000-000", (None, "invalido")),
    ("123", (None, "invalido")),
])
def test_cep(entrada, esperado):
    assert normalizar_cep(entrada) == esperado


# -------------------------------------------------------------------- cnpj
def test_cnpj_dv_conhecido():
    assert cnpj_dv_valido("11222333000181")
    assert not cnpj_dv_valido("11222333000182")
    assert not cnpj_dv_valido("00000000000000")


def test_cnpj_formata_e_sinaliza_dv():
    assert normalizar_cnpj("11222333000181") == ("11.222.333/0001-81", True, "ok")
    fmt, ok, crit = normalizar_cnpj("84.959.310/3413-16")
    assert fmt == "84.959.310/3413-16" and ok is False and "dv_invalido" in crit
    assert normalizar_cnpj("27868011280598")[0] == "27.868.011/2805-98"


def test_cnpj_tamanho_invalido():
    assert normalizar_cnpj("123") == (None, None, "invalido_tamanho")
    assert normalizar_cnpj("") == (None, None, "ausente")


# ---------------------------------------------------------------- telefone
@pytest.mark.parametrize("entrada,esperado", [
    ("61970855700", ("+5561970855700", "celular", "ok")),
    ("+55 61 95386-2084", ("+5561953862084", "celular", "ok")),
    ("(61) 98433-1053", ("+5561984331053", "celular", "ok")),
    ("(61) 3491-1634", ("+556134911634", "fixo", "ok")),
    ("61 3970-2193", ("+556139702193", "fixo", "ok")),
])
def test_telefone_validos(entrada, esperado):
    assert normalizar_telefone(entrada) == esperado


@pytest.mark.parametrize("entrada,criterio", [
    ("", "ausente"),
    ("12345", "invalido_tamanho"),
    ("(61) 91234-5678 9", "invalido_tamanho"),
    ("(10) 91234-5678", "invalido_ddd"),
    ("(61) 81234-5678", "invalido_celular_sem_9"),
    ("(61) 9123-4567", "invalido_fixo"),
])
def test_telefone_invalidos(entrada, criterio):
    assert normalizar_telefone(entrada) == (None, None, criterio)


# -------------------------------------------------------------------- data
@pytest.mark.parametrize("entrada,esperado", [
    ("2022-06-21", (date(2022, 6, 21), "iso", False)),
    ("28/02/2022", (date(2022, 2, 28), "dd/mm/aaaa", False)),
    ("15-08-2024", (date(2024, 8, 15), "dd-mm-aaaa", False)),
    ("Dec 24, 2023", (date(2023, 12, 24), "mes_abrev_dia_ano", False)),
    ("jul 21, 2022", (date(2022, 7, 21), "mes_abrev_dia_ano", False)),
    ("Apr 3, 2025", (date(2025, 4, 3), "mes_abrev_dia_ano", False)),
])
def test_datas_formatos(entrada, esperado):
    assert normalizar_data(entrada) == esperado


def test_data_ambigua_e_lida_como_dd_mm():
    assert normalizar_data("08-01-2022") == (date(2022, 1, 8), "dd-mm-aaaa", True)
    # dia == mês: a leitura mm/dd daria o mesmo resultado, logo não é ambígua
    assert normalizar_data("03/03/2021") == (date(2021, 3, 3), "dd/mm/aaaa", False)


@pytest.mark.parametrize("entrada,formato", [
    ("", "ausente"),
    ("31/02/2022", "data_invalida"),
    ("abc", "formato_desconhecido"),
    ("Xyz 3, 2022", "mes_desconhecido"),
])
def test_data_invalida(entrada, formato):
    assert normalizar_data(entrada) == (None, formato, False)


# ------------------------------------------------------------------- email
def test_email():
    assert normalizar_email(" Contato@Loja.com.br ") == ("contato@loja.com.br", True, "ok")
    email, ok, crit = normalizar_email("contato@comercialsão.com.br")
    assert email == "contato@comercialsão.com.br" and ok is False and "nao_ascii" in crit
    assert normalizar_email("") == (None, None, "ausente")
