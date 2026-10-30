# ETL — Distribuidora Vetor (Desafio Técnico 1)

Pipeline em Python que limpa e enriquece a base de clientes (bairro, CEP, CNPJ, telefone, data, e-mail),
grava em banco SQL e registra uma trilha de auditoria (valor original → valor tratado → critério/fonte).

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/vetor
python main.py            # ou: python main.py --sem-api --db-url sqlite:///vetor.db
pytest
```

- Documentação técnica: `docs/DOCUMENTACAO_TECNICA.md`
- Relatório de trade-offs: `docs/RELATORIO_TRADEOFFS.md`
- Dicionário de bairros (editável): `etl/dicionario_bairros.csv`
