# src/run_sql.py
import json, os, ssl, sys
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

C = pyexasol.connect(dsn="127.0.0.1:8563", user="sys",
                     password=find_pwd(json.load(open(SECRETS))),
                     encryption=True,
                     websocket_sslopt={"cert_reqs": ssl.CERT_NONE})

for f in sys.argv[1:]:
    print("Running", f)
    for stmt in open(f, encoding="utf-8").read().split(";"):
        if stmt.strip():
            C.execute(stmt)
    print("done")