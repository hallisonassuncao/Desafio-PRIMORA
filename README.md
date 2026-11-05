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
   
1. Entrar na pasta e ativar o ambiente
 cd C:\Users\Halli\Downloads\etl_vetor\etl_vetor

 python -m venv .venv
 
.venv\Scripts\Activate.ps1

1. pip install -r requirements.txt

1. pytest

2. Rodar o ETL no PostgreSQL (entrega oficial) usar a senha do postgres

$env:DATABASE_URL="postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/vetor"
python main.py

3. Testar o pipeline sem PostgreSQL e sem internet

python main.py --sem-api --db-url sqlite:///vetor.db

3. Rodar o ETL em SQLite (sem servidor)

pip install sqlalchemy
pip install requests
python main.py --db-url sqlite:///vetor.db

3.1 Crie o banco vetor no PostgreSQL local:

psql -U postgres -c "CREATE DATABASE vetor;"

Defina a URL de conexão, ajustando usuário, senha e porta ao seu ambiente:

# Linux
export DATABASE_URL=postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/vetor
# Windows 
$env:DATABASE_URL="postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/vetor"

Execute:

python main.py

5. Rodar os testes

pytest

Devem passar 76 testes.

6. Conferir o resultado no PostgreSQL

& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT bairro, COUNT(*) FROM clientes_tratados GROUP BY bairro ORDER BY 2 DESC;"

& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d vetor -c "SELECT * FROM auditoria_tratamento WHERE revisao_manual;"


7. Conferir o resultado no SQLite

python -c "import sqlite3; c=sqlite3.connect('vetor.db'); print(c.execute('SELECT bairro, COUNT(*) FROM clientes_tratados GROUP BY bairro').fetchall())"

Lembretes
