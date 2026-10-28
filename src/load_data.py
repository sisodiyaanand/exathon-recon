import argparse
import os
import ssl
import time

import pandas as pd
import pyexasol

SCHEMA = "RECON"
TABLES = {
    "LEDGER": ("ledger.csv", {"txn_id", "customer_id", "account_id", "device_id", "amount"}),
    "BANK_STATEMENT": ("bank_statement.csv", {"account_id", "amount"}),
    "FRAUD_TRUTH": ("fraud_truth.csv", {"txn_id", "is_fraud"}),
}


def connect():
    return pyexasol.connect(
        dsn=os.getenv("EXA_DSN", "localhost:8563"),
        user=os.getenv("EXA_USER", "sys"),
        password=os.getenv("EXA_PASSWORD", "exasol"),
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
        compression=True,
    )


def run_sql_file(conn, path):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.strip().startswith("--")]
    for stmt in "\n".join(lines).split(";"):
        if stmt.strip():
            conn.execute(stmt)


def sql_literal(value, numeric):
    if pd.isna(value):
        return "NULL"
    if numeric:
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_batched(conn, csv_path, table, numeric_cols, chunk=2000):
    total = 0
    for df in pd.read_csv(csv_path, dtype=str, chunksize=chunk):
        flags = [c in numeric_cols for c in df.columns]
        rows = []
        for rec in df.itertuples(index=False, name=None):
            rows.append("(" + ",".join(sql_literal(v, n) for v, n in zip(rec, flags)) + ")")
        conn.execute(f"INSERT INTO {SCHEMA}.{table} VALUES " + ",".join(rows))
        total += len(df)
        if total % 100_000 == 0:
            print(f"   {table}: {total:,} rows")


def load_table(conn, data_dir, table, method):
    csv_name, numeric_cols = TABLES[table]
    path = os.path.join(data_dir, csv_name)
    t0 = time.time()
    if method in ("auto", "import"):
        try:
            conn.execute(f"TRUNCATE TABLE {SCHEMA}.{table}")
            conn.import_from_file(path, (SCHEMA, table), import_params={"skip": 1})
            used = "IMPORT"
        except Exception as exc:
            if method == "import":
                raise
            print(f"   fast IMPORT failed ({type(exc).__name__}); using batched INSERT")
            conn.execute(f"TRUNCATE TABLE {SCHEMA}.{table}")
            insert_batched(conn, path, table, numeric_cols)
            used = "INSERT"
    else:
        conn.execute(f"TRUNCATE TABLE {SCHEMA}.{table}")
        insert_batched(conn, path, table, numeric_cols)
        used = "INSERT"
    n = conn.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}").fetchval()
    print(f"{table:<15} {n:>10,} rows via {used} in {time.time() - t0:.1f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--sql", default="sql/01_schema.sql")
    ap.add_argument("--method", choices=["auto", "import", "insert"], default="auto")
    a = ap.parse_args()

    conn = connect()
    print("Connected to Exasol")
    run_sql_file(conn, a.sql)
    print("Schema created")
    for table in TABLES:
        load_table(conn, a.data, table, a.method)
    conn.close()


if __name__ == "__main__":
    main()