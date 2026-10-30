"""Normalização determinística de campos (sem I/O, sem rede).

Cada função devolve o valor tratado + um critério textual que alimenta
a tabela de auditoria.
"""
import csv
import difflib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DICIONARIO_PADRAO = Path(__file__).with_name("dicionario_bairros.csv")


def sem_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


# ----------------------------------------------------------------- bairro
@dataclass
class ResultadoBairro:
    bairro: str | None
    subdivisao: str | None
    criterio: str  # vazio | dicionario | fuzzy | nao_mapeado
    revisao_manual: bool = False


def carregar_dicionario(caminho: Path | str | None = None) -> dict[str, tuple[str, str | None]]:
    """variante normalizada -> (bairro canônico, subdivisão)."""
    caminho = Path(caminho) if caminho else DICIONARIO_PADRAO
    dicionario = {}
    with open(caminho, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            dicionario[linha["variante"].strip()] = (
                linha["bairro"].strip(),
                (linha["subdivisao"] or "").strip() or None,
            )
    return dicionario


def chave_texto(valor: str | None) -> str:
    """Caixa, acentos, parênteses, sufixo DF e pontuação -> chave comparável."""
    t = sem_acentos(valor or "").lower()
    t = re.sub(r"[()]", " ", t)
    t = re.sub(r"\b(df|distrito federal)\b", " ", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalizar_bairro(valor, dicionario, corte_fuzzy: float = 0.88) -> ResultadoBairro:
    chave = chave_texto(valor)
    if not chave:
        return ResultadoBairro(None, None, "vazio")
    if chave in dicionario:
        bairro, sub = dicionario[chave]
        return ResultadoBairro(bairro, sub, "dicionario")
    parecidos = difflib.get_close_matches(chave, dicionario.keys(), n=1, cutoff=corte_fuzzy)
    if parecidos:
        bairro, sub = dicionario[parecidos[0]]
        return ResultadoBairro(bairro, sub, "fuzzy", revisao_manual=True)
    return ResultadoBairro(None, None, "nao_mapeado", revisao_manual=True)


# -------------------------------------------------------------------- cep
def normalizar_cep(valor) -> tuple[str | None, str]:
    """-> (cep formatado | None, status: ok | ausente | invalido)."""
    d = re.sub(r"\D", "", valor or "")
    if not d:
        return None, "ausente"
    if len(d) != 8 or len(set(d)) == 1:  # 00000-000 e similares
        return None, "invalido"
    return f"{d[:5]}-{d[5:]}", "ok"


# ------------------------------------------------------------------- cnpj
def cnpj_dv_valido(digitos: str) -> bool:
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False

    def dv(base: str) -> str:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
        resto = sum(int(x) * p for x, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = dv(digitos[:12])
    d2 = dv(digitos[:12] + d1)
    return digitos[12:] == d1 + d2


def normalizar_cnpj(valor) -> tuple[str | None, bool | None, str]:
    """-> (cnpj formatado | None, dv_valido | None, critério).

    CNPJ com 14 dígitos é padronizado mesmo que o DV falhe (apenas sinalizado).
    """
    d = re.sub(r"\D", "", valor or "")
    if not d:
        return None, None, "ausente"
    if len(d) != 14:
        return None, None, "invalido_tamanho"
    fmt = f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    ok = cnpj_dv_valido(d)
    return fmt, ok, "ok" if ok else "dv_invalido_mantido_e_sinalizado"


# --------------------------------------------------------------- telefone
def normalizar_telefone(valor) -> tuple[str | None, str | None, str]:
    """-> (E.164 | None, tipo celular|fixo | None, critério)."""
    d = re.sub(r"\D", "", valor or "")
    if not d:
        return None, None, "ausente"
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) not in (10, 11):
        return None, None, "invalido_tamanho"
    if not 11 <= int(d[:2]) <= 99:
        return None, None, "invalido_ddd"
    numero = d[2:]
    if len(numero) == 9:
        if numero[0] != "9":
            return None, None, "invalido_celular_sem_9"
        tipo = "celular"
    else:
        if numero[0] not in "2345":
            return None, None, "invalido_fixo"
        tipo = "fixo"
    return f"+55{d}", tipo, "ok"


# ------------------------------------------------------------------- data
MESES = {
    "jan": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "abr": 4, "may": 5, "mai": 5,
    "jun": 6, "jul": 7, "aug": 8, "ago": 8, "sep": 9, "set": 9, "oct": 10, "out": 10,
    "nov": 11, "dec": 12, "dez": 12,
}


def normalizar_data(valor) -> tuple[date | None, str, bool]:
    """-> (data | None, formato detectado, ambigua).

    Formatos com barra/hífen são lidos como dd/mm/aaaa (padrão brasileiro).
    `ambigua` = dia e mês ambos <= 12 e diferentes (a leitura mm/dd mudaria a data).
    """
    v = (valor or "").strip()
    if not v:
        return None, "ausente", False
    try:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            return date(int(m[1]), int(m[2]), int(m[3])), "iso", False
        m = re.fullmatch(r"(\d{2})([/-])(\d{2})\2(\d{4})", v)
        if m:
            dia, mes, ano = int(m[1]), int(m[3]), int(m[4])
            ambigua = dia <= 12 and mes <= 12 and dia != mes
            formato = "dd/mm/aaaa" if m[2] == "/" else "dd-mm-aaaa"
            return date(ano, mes, dia), formato, ambigua
        m = re.fullmatch(r"([A-Za-z]{3,4})\.? (\d{1,2}), (\d{4})", v)
        if m:
            mes = MESES.get(m[1].lower()[:3])
            if mes is None:
                return None, "mes_desconhecido", False
            return date(int(m[3]), mes, int(m[2])), "mes_abrev_dia_ano", False
    except ValueError:
        return None, "data_invalida", False
    return None, "formato_desconhecido", False


# ------------------------------------------------------------------ email
EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+")


def normalizar_email(valor) -> tuple[str | None, bool | None, str]:
    """Apenas minúsculas/trim + validação de formato; nunca "corrige" o endereço."""
    e = (valor or "").strip().lower()
    if not e:
        return None, None, "ausente"
    if EMAIL_RE.fullmatch(e):
        return e, True, "ok"
    return e, False, "formato_invalido_ou_nao_ascii_mantido_e_sinalizado"
