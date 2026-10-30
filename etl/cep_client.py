"""Consulta de CEP (ViaCEP -> BrasilAPI) com cache local em SQLite.

- Cache positivo e negativo ("CEP não existe") para não repetir chamadas.
- Falha de rede/5xx NÃO é cacheada: na próxima execução tenta de novo.
- A sessão HTTP é injetável, então os testes simulam as APIs (sem rede real).
"""
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

_AUSENTE = object()


@dataclass
class ConsultaCep:
    cep: str
    bairro: str
    localidade: str
    uf: str
    fonte: str


class _Falha(Exception):
    """Erro transitório (rede, timeout, HTTP 5xx/429, JSON inválido)."""


def _formatar(cep8: str) -> str:
    return f"{cep8[:5]}-{cep8[5:]}"


def _consultar_viacep(sessao, cep8, timeout):
    try:
        r = sessao.get(f"https://viacep.com.br/ws/{cep8}/json/", timeout=timeout)
        if r.status_code == 400:
            return None
        if r.status_code != 200:
            raise _Falha(f"viacep http {r.status_code}")
        d = r.json()
    except (requests.RequestException, ValueError) as e:
        raise _Falha(str(e)) from e
    if d.get("erro"):
        return None
    return ConsultaCep(_formatar(cep8), d.get("bairro") or "", d.get("localidade") or "",
                       d.get("uf") or "", "viacep")


def _consultar_brasilapi(sessao, cep8, timeout):
    try:
        r = sessao.get(f"https://brasilapi.com.br/api/cep/v1/{cep8}", timeout=timeout)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise _Falha(f"brasilapi http {r.status_code}")
        d = r.json()
    except (requests.RequestException, ValueError) as e:
        raise _Falha(str(e)) from e
    return ConsultaCep(_formatar(cep8), d.get("neighborhood") or "", d.get("city") or "",
                       d.get("state") or "", "brasilapi")


class ClienteCep:
    def __init__(self, caminho_cache="cache/cep_cache.sqlite", sessao=None, timeout=5, pausa=0.0):
        Path(caminho_cache).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(caminho_cache)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cep_cache (cep TEXT PRIMARY KEY, encontrado INTEGER,"
            " bairro TEXT, localidade TEXT, uf TEXT, fonte TEXT, consultado_em TEXT)"
        )
        self._sessao = sessao or requests.Session()
        self._timeout = timeout
        self._pausa = pausa
        self._provedores = (_consultar_viacep, _consultar_brasilapi)
        self.stats = {"cache": 0, "api": 0, "falhas": 0}

    def consultar(self, cep: str) -> ConsultaCep | None:
        cep8 = re.sub(r"\D", "", cep)
        em_cache = self._ler_cache(cep8)
        if em_cache is not _AUSENTE:
            self.stats["cache"] += 1
            return em_cache

        encontrados, houve_falha = [], False
        for consulta in self._provedores:
            try:
                resultado = consulta(self._sessao, cep8, self._timeout)
            except _Falha:
                houve_falha = True
                self.stats["falhas"] += 1
                continue
            finally:
                if self._pausa:
                    time.sleep(self._pausa)
            self.stats["api"] += 1
            if resultado:
                encontrados.append(resultado)
                if resultado.bairro:
                    break

        if encontrados:
            melhor = next((r for r in encontrados if r.bairro), encontrados[0])
            self._gravar_cache(cep8, melhor)
            return melhor
        if not houve_falha:  # todos os provedores responderam "não existe"
            self._gravar_cache(cep8, None)
        return None

    def _ler_cache(self, cep8):
        linha = self._db.execute(
            "SELECT encontrado, bairro, localidade, uf, fonte FROM cep_cache WHERE cep=?", (cep8,)
        ).fetchone()
        if linha is None:
            return _AUSENTE
        if not linha[0]:
            return None
        return ConsultaCep(_formatar(cep8), linha[1], linha[2], linha[3], linha[4])

    def _gravar_cache(self, cep8, c: ConsultaCep | None):
        agora = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            "INSERT OR REPLACE INTO cep_cache VALUES (?,?,?,?,?,?,?)",
            (cep8, int(c is not None), c and c.bairro, c and c.localidade, c and c.uf,
             c and c.fonte, agora),
        )
        self._db.commit()

    def fechar(self):
        self._db.close()
