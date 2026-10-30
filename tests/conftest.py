import pytest
from etl.normalizers import carregar_dicionario


@pytest.fixture(scope="session")
def dicionario():
    return carregar_dicionario()


class RespostaFalsa:
    def __init__(self, status=200, corpo=None, erro_json=False):
        self.status_code = status
        self._corpo = corpo
        self._erro_json = erro_json

    def json(self):
        if self._erro_json:
            raise ValueError("json inválido")
        return self._corpo


class SessaoFalsa:
    """Simula requests.Session: mapeia fragmento de URL -> resposta ou exceção. Nunca usa rede."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    def get(self, url, timeout=None):
        self.chamadas.append(url)
        for trecho, resp in self.respostas.items():
            if trecho in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f"chamada inesperada: {url}")
