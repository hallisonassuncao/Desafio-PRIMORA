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

- $env:DATABASE_URL="postgresql+psycopg2://postgres:607337@localhost:5432/vetor"
python main.py

.venv\Scripts\Activate.ps1    

1. Entrar na pasta e ativar o ambiente

powershell
cd C:\Users\Halli\Downloads\etl_vetor\etl_vetor
.venv\Scripts\Activate.ps1

2. Rodar o ETL no PostgreSQL (entrega oficial)

powershell
$env:DATABASE_URL="postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/vetor"
python main.py

3. Rodar o ETL em SQLite (sem servidor)

powershell
python main.py --db-url sqlite:///vetor.db

4. Rodar offline, sem consultar a API de CEP

powershell
python main.py --sem-api --db-url sqlite:///vetor.db

5. Rodar os testes

pytest

Devem passar 76 testes.

6. Conferir o resultado no PostgreSQL

Bairros agrupados:

powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT bairro, COUNT(*) FROM clientes_tratados GROUP BY bairro ORDER BY 2 DESC;"

Auditoria (primeiras linhas):

powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT id_cliente, campo, valor_original, valor_tratado, criterio FROM auditoria_tratamento LIMIT 15;"

Divergências entre CEP e bairro:

powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT id_cliente, bairro_informado, bairro FROM clientes_tratados WHERE divergencia_cep_bairro;"

7. Conferir o resultado no SQLite

powershell
python -c "import sqlite3; c=sqlite3.connect('vetor.db'); print(c.execute('SELECT bairro, COUNT(*) FROM clientes_tratados GROUP BY bairro').fetchall())"

Lembretes
