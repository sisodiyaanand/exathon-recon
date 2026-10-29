import json, os, ssl, sys, time
import pyexasol

SECRETS = os.path.expanduser(r"~\.exasol\personal\deployments\default\secrets.json")

def find_pwd(d):
    for k, v in d.items():
        if isinstance(v, dict):
            r = find_pwd(v)
            if r:
                return r
        elif "password" in k.lower() and isinstance(v, str):
            return v

secrets = json.load(open(SECRETS))
pwd = find_pwd(secrets)
if not pwd:
    print("Password key nahi mila. secrets.json ki keys:", list(secrets.keys()))
    sys.exit(1)

C = pyexasol.connect(
    dsn="127.0.0.1:8563", user="sys", password=pwd,
    encryption=True, websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
)

# 1. Schema + tables
for stmt in open("sql/01_schema.sql", encoding="utf-8").read().split(";"):
    if stmt.strip():
        C.execute(stmt)
print("Schema ready")

# 2. Load CSVs
def row_sep(path):
    with open(path, "rb") as f:
        return "CRLF" if b"\r\n" in f.read(2000) else "LF"

for fname, table in [
    ("ledger.csv", "LEDGER"),
    ("bank_statement.csv", "BANK_STATEMENT"),
    ("fraud_truth.csv", "FRAUD_TRUTH"),
]:
    path = os.path.join("data", fname)
    t = time.time()
    C.import_from_file(path, ("RECON", table),
                       import_params={"skip": 1, "row_separator": row_sep(path)})
    n = C.execute(f"SELECT COUNT(*) FROM RECON.{table}").fetchone()[0]
    print(f"{table}: {n} rows ({time.time()-t:.0f}s)")