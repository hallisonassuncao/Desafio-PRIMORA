# ETL — Distribuidora Vetor (Desafio Técnico 1) Desafio PRIMORA

Pipeline em Python que limpa e enriquece a base de clientes (bairro, CEP, CNPJ, telefone, data, e-mail),
grava em banco SQL e registra uma trilha de auditoria (valor original → valor tratado → critério/fonte).

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/vetor
python main.py            # ou: python main.py --sem-api --db-url sqlite:///vetor.db
pytest
```

- Documentação técnica: 
- Relatório de trade-offs: 
- Dicionário de bairros (editável):

- $env:DATABASE_URL="postgresql+psycopg2://postgres:607337@localhost:5432/vetor"
python main.py

.venv\Scripts\Activate.ps1    

1. Entrar na pasta e ativar o ambiente


cd C:\Users\Halli\Downloads\etl_vetor\etl_vetor
.venv\Scripts\Activate.ps1

2. Rodar o ETL no PostgreSQL (entrega oficial)


$env:DATABASE_URL="postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/vetor"
python main.py

3. Rodar o ETL em SQLite (sem servidor)


python main.py --db-url sqlite:///vetor.db

4. Rodar offline, sem consultar a API de CEP


python main.py --sem-api --db-url sqlite:///vetor.db

5. Rodar os testes

pytest

Devem passar 76 testes.

6. Conferir o resultado no PostgreSQL

Bairros agrupados:


 "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT bairro, COUNT(*) FROM clientes_tratados GROUP BY bairro ORDER BY 2 DESC;"

Auditoria (primeiras linhas):


 "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT id_cliente, campo, valor_original, valor_tratado, criterio FROM auditoria_tratamento LIMIT 15;"

Divergências entre CEP e bairro:


"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT id_cliente, bairro_informado, bairro FROM clientes_tratados WHERE divergencia_cep_bairro;"

7. Conferir o resultado no SQLite

powershell
python -c "import sqlite3; c=sqlite3.connect('vetor.db'); print(c.execute('SELECT bairro, COUNT(*) FROM clientes_tratados GROUP BY bairro').fetchall())"

Lembretes
