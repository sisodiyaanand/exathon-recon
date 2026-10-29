import json, os, ssl
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

QUERIES = {
 "RECON SUMMARY": "SELECT * FROM RECON.RECON_SUMMARY ORDER BY TXN_CNT DESC",
 "FRAUD METRICS (HIGH band)": "SELECT * FROM RECON.FRAUD_METRICS",
 "RISK BANDS": "SELECT RISK_BAND, COUNT(*) AS CNT FROM RECON.FRAUD_SCORES GROUP BY RISK_BAND ORDER BY CNT DESC",
 "FRAUD PATTERNS CAUGHT": """
    SELECT t.PATTERN, COUNT(*) AS TOTAL,
           SUM(CASE WHEN s.RISK_BAND = 'HIGH' THEN 1 ELSE 0 END) AS CAUGHT_HIGH
    FROM RECON.FRAUD_TRUTH t JOIN RECON.FRAUD_SCORES s ON s.TXN_ID = t.TXN_ID
    WHERE t.IS_FRAUD = 1 GROUP BY t.PATTERN ORDER BY TOTAL DESC""",
 "TOP 10 HIGH RISK": """
    SELECT TXN_ID, CUSTOMER_ID, AMOUNT, CITY, SCORE, REASONS
    FROM RECON.FRAUD_SCORES ORDER BY SCORE DESC, AMOUNT DESC LIMIT 10""",
}

for title, q in QUERIES.items():
    st = C.execute(q)
    print("\n==", title, "==")
    print(" | ".join(st.columns().keys()))
    for row in st.fetchall():
        print(" | ".join(str(x) for x in row))