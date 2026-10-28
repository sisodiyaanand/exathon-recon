"""Run reconciliation + fraud scoring inside Exasol and print the results."""
import time

import pandas as pd

from db import connect, query_df, run_sql_file

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)


def main():
    conn = connect()
    t0 = time.time()
    for path in ("sql/02_reconcile.sql", "sql/03_fraud.sql"):
        print(f"\n== {path}")
        run_sql_file(conn, path)
    print(f"\nPipeline finished in {time.time() - t0:.1f}s (all logic ran inside Exasol)")

    print("\n== Reconciliation summary")
    summary = query_df(conn, "SELECT * FROM RECON.RECON_SUMMARY ORDER BY TXN_CNT DESC")
    print(summary.to_string(index=False))
    total = query_df(conn, "SELECT COUNT(*) AS N FROM RECON.LEDGER")["N"].iloc[0]
    ok = summary.loc[summary["STATUS"].isin(["MATCHED", "MATCHED_FUZZY"]), "TXN_CNT"].sum()
    print(f"\nAuto-matched without human touch: {ok:,} of {total:,} ({ok / total:.1%})")

    print("\n== Fraud detection accuracy (HIGH band vs ground truth)")
    print(query_df(conn, "SELECT * FROM RECON.FRAUD_METRICS").to_string(index=False))

    print("\n== Top 5 risk alerts")
    top = query_df(
        conn,
        "SELECT TXN_ID, CUSTOMER_ID, AMOUNT, CITY, SCORE, RISK_BAND, REASONS "
        "FROM RECON.FRAUD_SCORES ORDER BY SCORE DESC, AMOUNT DESC LIMIT 5",
    )
    print(top.to_string(index=False))
    conn.close()


if __name__ == "__main__":
    main()
