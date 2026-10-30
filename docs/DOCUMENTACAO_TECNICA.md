# Documentação técnica — ETL da base de clientes (Distribuidora Vetor)

## 1. Visão geral

```
CSV (;) ──► extrair ──► transformar ──► carregar ──► PostgreSQL
                          │   ▲                         ├─ clientes_tratados
                          │   └── ClienteCep            └─ auditoria_tratamento
                          │       (ViaCEP → BrasilAPI,
                          │        cache SQLite local)
                          └─► dicionario_bairros.csv (variante → bairro canônico)
```

| Módulo | Responsabilidade |
|---|---|
| `etl/normalizers.py` | Funções puras de normalização (bairro, CEP, CNPJ, telefone, data, e-mail) |
| `etl/cep_client.py` | Consulta de CEP com fallback entre provedores e cache local |
| `etl/resolucao.py` | Critério explícito para combinar bairro informado × bairro da API |
| `etl/pipeline.py` | Extração, transformação, carga e resumo; define as tabelas |
| `etl/dicionario_bairros.csv` | Dicionário variante → bairro canônico (+ subdivisão), ampliável sem mexer em código |
| `main.py` | CLI |

## 2. Como executar

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/vetor
python main.py                      # com consulta de CEP (internet)
python main.py --sem-api --db-url sqlite:///vetor.db   # offline, sem PostgreSQL
pytest                              # 74 testes, sem rede e sem PostgreSQL
```

Saídas: tabelas no banco + `saida/clientes_tratados.csv` + `saida/auditoria_tratamento.csv`
+ resumo em JSON no terminal. A carga é uma **recarga completa e atômica** (uma transação):
reexecutar não duplica linhas.

## 3. Regras de tratamento

### 3.1 Bairro
1. **Chave textual**: minúsculas, sem acentos, sem parênteses, sem sufixo `DF`, pontuação vira espaço
   (`"Sul (Águas Claras)"` → `"sul aguas claras"`; `"Taguatinga - DF"` → `"taguatinga"`).
2. **Dicionário**: a chave é procurada em `dicionario_bairros.csv`, que devolve *bairro canônico* e
   *subdivisão*. Ex.: `sul aguas claras` → (`Águas Claras`, `Sul`); `vte pires` → (`Vicente Pires`, `—`).
3. **Fuzzy (rede de segurança)**: chave fora do dicionário, mas com similaridade ≥ 0,88 com uma entrada
   (`difflib`), é mapeada **e marcada para revisão manual** (`criterio = fuzzy`).
4. **Não mapeado**: bairro nulo, `revisao_manual = true`. Nada é inventado.

**Bairro-pai × subdivisão.** O relatório agrega pelo bairro-pai (`bairro`); a subdivisão informal
(Sul/Norte, I/II) fica em coluna própria (`subdivisao`) e não se perde.

### 3.2 CEP e enriquecimento
- CEP é padronizado para `NNNNN-NNN`. Vazio → `ausente`; tamanho errado ou todos os dígitos iguais
  (`00000-000`) → `invalido`. Só CEPs `ok` são consultados.
- Consulta: **ViaCEP** primeiro; se falhar (timeout, 5xx, JSON inválido) ou vier sem bairro, **BrasilAPI**.
- **Cache local** (SQLite, `cache/cep_cache.sqlite`): guarda acertos e também "CEP não existe"
  (cache negativo). **Falhas de rede nunca são cacheadas**, para não gravar um "não existe" falso.
- Resposta com UF diferente da do cadastro é **ignorada** e vai para revisão manual.
- O bairro devolvido pela API passa pelo mesmo normalizador/dicionário que o bairro informado.

### 3.3 Critério de divergência (bairro informado × API)

| Situação | Bairro final | Fonte | Flags |
|---|---|---|---|
| Sem resposta utilizável da API (CEP ausente/inválido, API fora do ar, CEP inexistente) | informado (se mapeado) | `informado` | — |
| Informado ausente ou não mapeado, API mapeada | API | `api_cep` | — |
| Ambos mapeados, mesmo bairro-pai | API; subdivisão = informada, senão a da API | `api_cep+informado` | — |
| Ambos mapeados, bairros-pai diferentes | **API prevalece** | `api_cep` | `divergencia_cep_bairro = true` |
| Bairro da API fora do dicionário | informado | `informado` | `revisao_manual = true` |

Justificativa: o CEP é uma fonte estruturada e verificável; o bairro é texto livre digitado por
vendedores. Em contrapartida, um CEP errado digitado com bairro certo seria "corrigido" para errado —
por isso a divergência é sempre sinalizada e auditada, nunca silenciosa.

### 3.4 Demais campos
| Campo | Regra | Não faz |
|---|---|---|
| CNPJ | Remove pontuação, exige 14 dígitos, formata `XX.XXX.XXX/XXXX-XX`, valida dígitos verificadores → `cnpj_dv_valido` | Não descarta CNPJ com DV inválido (ver §5) |
| Telefone | Remove `+55`/máscara; 10 dígitos = fixo (inicia 2–5), 11 = celular (inicia 9); DDD 11–99; saída E.164 `+55DDNNNNNNNNN` | Não adivinha dígito faltante |
| Data | ISO, `dd/mm/aaaa`, `dd-mm-aaaa` e `Mon d, aaaa` (meses em inglês/português abreviados); saída `DATE` | Não usa `locale` do SO |
| E-mail | trim + minúsculas + validação de formato (`email_valido`) | Não corrige o endereço |
| Razão social | Colapsa espaços | — |

**Premissa de negócio (assumida e documentada):** datas com `/` ou `-` são `dd/mm/aaaa`
(padrão brasileiro). Quando dia e mês são ambos ≤ 12 e diferentes, a leitura `mm/dd` mudaria a data;
esses casos recebem `data_ambigua = true` (no CSV fornecido: 6 registros).

## 4. Modelo de dados

`clientes_tratados` (1 linha por cliente): campos tratados + `bairro_informado` (original),
`bairro`, `subdivisao`, `bairro_fonte`, `divergencia_cep_bairro`, `revisao_manual`,
`cnpj_dv_valido`, `email_valido`, `telefone_tipo`, `cep_status`, `data_ambigua`.

`auditoria_tratamento`: `id_cliente`, `campo`, `valor_original`, `valor_tratado`, `criterio`, `fonte`
(`regra`, `informado`, `api_cep`, `api_cep+informado`), `revisao_manual`, `executado_em`.
Registra toda alteração de valor e todo critério diferente de "ok", inclusive a resposta da API
(`api=viacep: 'Taguatinga Sul'`) no campo `criterio` do bairro.

Exemplos (execução offline):

| id | campo | original | tratado | critério |
|---|---|---|---|---|
| CLI0001 | bairro | `Sul (Águas Claras)` | `Águas Claras / Sul` | `informado_sem_confirmacao_de_cep` |
| CLI0003 | data_cadastro | `28/02/2022` | `2022-02-28` | `formato=dd/mm/aaaa` |
| CLI0005 | cep | `00000-000` | *(nulo)* | `cep_invalido` |
| CLI0001 | cnpj | `84.959.310/3413-16` | idem | `dv_invalido_mantido_e_sinalizado` |

## 5. Limites conhecidos

1. **CNPJ**: nenhum dos 47 CNPJs da base passa na validação dos dígitos verificadores (base sintética).
   Rejeitá-los esvaziaria a tabela; por isso são padronizados e sinalizados. Em produção a regra deve
   ser revista (quarentena ou rejeição).
2. **Dicionário construído a partir desta amostra** (47 linhas): bairros fora dela cairão em
   `nao_mapeado`/`fuzzy` e exigirão revisão manual para entrar no dicionário.
3. **CEP em Brasília é pouco granular**: vários CEPs cobrem quadras/áreas amplas, e o nome de bairro
   devolvido pelas APIs pode ser genérico, vazio ou diferente do nome popular (ex.: "Setor ...").
   Nesses casos o pipeline mantém o informado e pede revisão, mas a **qualidade real das respostas
   de ViaCEP/BrasilAPI para estes CEPs não foi medida** (ver §6).
4. **Subdivisões** (Sul/Norte, I/II) são mantidas como informadas; não há fonte oficial no pipeline
   que as confirme.
5. **Datas ambíguas** seguem a premissa `dd/mm`; sem uma segunda fonte, não há como confirmar.
6. **Telefone**: valida formato e DDD, não se o número existe.
7. **Fuzzy** é heurístico: pode aproximar nomes de bairros diferentes e semelhantes — por isso sempre
   exige revisão.
8. Carga em recarga completa: adequada ao tamanho do desafio; para grandes volumes seria preciso upsert/incremental.

## 6. O que foi e o que não foi verificado

- **Verificado**: 74 testes automatizados (normalização, cliente de CEP com respostas simuladas —
  sucesso, fallback, timeout, cache positivo/negativo, JSON inválido —, regras de resolução e pipeline
  ponta a ponta com o CSV real); execução completa em modo `--sem-api` com SQLite.
- **Não verificado**: chamadas reais a ViaCEP/BrasilAPI (o ambiente de desenvolvimento não tinha esses
  domínios liberados) e carga em PostgreSQL real (o código usa SQLAlchemy e tipos portáveis, testado
  em SQLite). Rodar `python main.py` no ambiente do desafio é o primeiro passo de validação, e o
  resumo impresso (`divergencias_cep_bairro`, `revisao_manual`, `cache_cep`) mostra imediatamente
  como as APIs se comportaram.
