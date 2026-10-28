import os
import ssl
import time

import pandas as pd
import pyexasol


def connect():
    return pyexasol.connect(
        dsn=os.getenv("EXA_DSN", "localhost:8563"),
        user=os.getenv("EXA_USER", "sys"),
        password=os.getenv("EXA_PASSWORD", "exasol"),
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
        compression=True,
    )


def run_sql_file(conn, path, verbose=True):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.strip().startswith("--")]
    for stmt in "\n".join(lines).split(";"):
        if not stmt.strip():
            continue
        t0 = time.time()
        conn.execute(stmt)
        if verbose:
            first = " ".join(stmt.split())[:70]
            print(f"   {time.time() - t0:6.1f}s  {first}")


def query_df(conn, sql):
    stmt = conn.execute(sql)
    df = pd.DataFrame(stmt.fetchall(), columns=stmt.column_names())
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            before = df[col].notna().sum()
            try:
                converted = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                continue
            if converted.notna().sum() == before:
                df[col] = converted
    return df