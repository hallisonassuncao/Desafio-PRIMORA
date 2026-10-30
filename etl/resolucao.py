"""Critério explícito para combinar o bairro informado com o bairro da API de CEP."""
from dataclasses import dataclass

from .normalizers import ResultadoBairro


@dataclass
class BairroResolvido:
    bairro: str | None
    subdivisao: str | None
    fonte: str          # api_cep | informado | api_cep+informado | nenhuma
    criterio: str
    divergencia: bool = False
    revisao_manual: bool = False


def resolver_bairro(informado: ResultadoBairro, api: ResultadoBairro | None) -> BairroResolvido:
    """`api` é None quando não houve consulta (sem CEP válido, sem rede ou CEP inexistente).

    Regras:
      1. Sem resposta utilizável da API -> vale o bairro informado (se mapeado).
      2. Informado ausente/não mapeado e API mapeada -> vale a API.
      3. Os dois mapeados e do mesmo bairro-pai -> concordam (subdivisão: informada, senão API).
      4. Os dois mapeados e bairros-pai diferentes -> a API prevalece e marca divergência.
    Fuzzy / não mapeado (do informado ou da API) pedem revisão manual.
    """
    api_ok = api is not None and api.bairro is not None
    inf_ok = informado.bairro is not None
    revisao_api = api is not None and api.revisao_manual

    if not api_ok:
        revisao = informado.revisao_manual or revisao_api
        if inf_ok:
            return BairroResolvido(informado.bairro, informado.subdivisao, "informado",
                                   "informado_sem_confirmacao_de_cep", False, revisao)
        return BairroResolvido(None, None, "nenhuma", "sem_bairro_resolvido", False,
                               revisao or informado.criterio != "vazio")

    if not inf_ok:
        return BairroResolvido(api.bairro, api.subdivisao, "api_cep",
                               "informado_ausente_ou_nao_mapeado_usa_api", False,
                               revisao_api)

    if informado.bairro == api.bairro:
        return BairroResolvido(api.bairro, informado.subdivisao or api.subdivisao,
                               "api_cep+informado", "concordam", False,
                               informado.revisao_manual or revisao_api)

    return BairroResolvido(api.bairro, api.subdivisao, "api_cep",
                           "divergencia_api_prevalece", True,
                           informado.revisao_manual or revisao_api)
