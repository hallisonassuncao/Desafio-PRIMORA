"""CLI do pipeline ETL.

Exemplos:
  python main.py                                   # PostgreSQL via DATABASE_URL + APIs de CEP
  python main.py --sem-api --db-url sqlite:///vetor.db   # offline, sem banco PostgreSQL
"""
import argparse
import csv
import json
import os
from pathlib import Path

from sqlalchemy import create_engine

from etl.cep_client import ClienteCep
from etl.pipeline import executar, resumir

DB_PADRAO = "postgresql+psycopg2://postgres:postgres@localhost:5432/vetor"


def exportar_csv(caminho, linhas):
    if not linhas:
        return
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(linhas)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--csv", default="data/clientes_distribuidora_vetor.csv")
    p.add_argument("--db-url", default=os.getenv("DATABASE_URL", DB_PADRAO))
    p.add_argument("--cache", default="cache/cep_cache.sqlite")
    p.add_argument("--dicionario", default=None)
    p.add_argument("--saida", default="saida", help="pasta dos CSVs exportados")
    p.add_argument("--sem-api", action="store_true", help="não consulta ViaCEP/BrasilAPI")
    args = p.parse_args()

    cliente_cep = None if args.sem_api else ClienteCep(args.cache)
    engine = create_engine(args.db_url)
    linhas, clientes, auditoria = executar(args.csv, engine, cliente_cep, args.dicionario)

    Path(args.saida).mkdir(parents=True, exist_ok=True)
    exportar_csv(Path(args.saida) / "clientes_tratados.csv", clientes)
    exportar_csv(Path(args.saida) / "auditoria_tratamento.csv", auditoria)
    print(json.dumps(resumir(linhas, clientes, auditoria, cliente_cep),
                     ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
