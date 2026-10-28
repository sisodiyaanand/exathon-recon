import time

import streamlit as st

from db import connect, query_df, run_sql_file

st.set_page_config(page_title="Recon & Fraud Console", layout="wide")


@st.cache_resource
def get_conn():
    return connect()


@st.cache_data(ttl=300, show_spinner=False)
def q(sql: str):
    return query_df(get_conn(), sql)


st.title("Reconciliation & Fraud Risk Console")

with st.sidebar:
    st.header("Exasol pipeline")
    st.write("Matching + fraud scoring run as SQL inside Exasol Personal.")
    if st.button("Re-run full pipeline", type="primary"):
        t0 = time.time()
        with st.spinner("Running inside Exasol..."):
            for path in ("sql/02_reconcile.sql", "sql/03_fraud.sql"):
                run_sql_file(get_conn(), path, verbose=False)
            st.cache_data.clear()
        st.success(f"Done in {time.time() - t0:.1f}s")

try:
    total = int(q("SELECT COUNT(*) AS N FROM RECON.LEDGER")["N"].iloc[0])
    summary = q("SELECT * FROM RECON.RECON_SUMMARY ORDER BY TXN_CNT DESC")
    metrics = q("SELECT * FROM RECON.FRAUD_METRICS").iloc[0]
except Exception as exc:
    st.error("Tables not found. Run `python src/run_pipeline.py` first.")
    st.caption(str(exc))
    st.stop()

st.caption(f"{total:,} ledger transactions reconciled against the bank statement and risk-scored.")

tab_rec, tab_fraud = st.tabs(["Reconciliation", "Fraud risk"])

with tab_rec:
    good = ["MATCHED", "MATCHED_FUZZY"]
    ok = int(summary.loc[summary["STATUS"].isin(good), "TXN_CNT"].sum())
    breaks = summary[~summary["STATUS"].isin(good)]
    open_cnt = int(breaks["TXN_CNT"].sum())
    money = float(breaks["AMOUNT_IN_QUESTION"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ledger transactions", f"{total:,}")
    c2.metric("Auto-matched", f"{ok / total:.1%}")
    c3.metric("Open breaks", f"{open_cnt:,}")
    c4.metric("Amount in question", f"Rs {money / 1e7:.2f} Cr")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Outcome of matching")
        st.bar_chart(summary.set_index("STATUS")["TXN_CNT"])
    with right:
        st.subheader("Break explorer")
        status = st.selectbox("Break type", list(breaks["STATUS"]))
        st.dataframe(
            q(
                "SELECT r.TXN_ID, r.BANK_REF, r.VARIANCE_AMT, r.MATCH_TYPE, "
                "l.ACCOUNT_ID, l.TXN_TS "
                "FROM RECON.RECON_RESULT r LEFT JOIN RECON.LEDGER l ON l.TXN_ID = r.TXN_ID "
                f"WHERE r.STATUS = '{status}' ORDER BY ABS(r.VARIANCE_AMT) DESC LIMIT 200"
            ),
            width="stretch",
            hide_index=True,
        )
    st.caption(
        "MATCHED: reference + amount equal. MATCHED_FUZZY: reference lost, matched on account + "
        "amount + date. AMOUNT_MISMATCH: fees/FX. MISSING_IN_BANK: never settled. "
        "DUPLICATE_POSTING: bank posted twice. UNMATCHED_BANK: bank entry with no ledger record."
    )

with tab_fraud:
    bands = q("SELECT RISK_BAND, COUNT(*) AS N FROM RECON.FRAUD_SCORES GROUP BY RISK_BAND")
    n_high = int(bands.loc[bands["RISK_BAND"] == "HIGH", "N"].sum())
    n_med = int(bands.loc[bands["RISK_BAND"] == "MEDIUM", "N"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("HIGH alerts", f"{n_high:,}")
    c2.metric("Review queue (MEDIUM)", f"{n_med:,}")
    c3.metric("Precision", f"{float(metrics['PRECISION_PCT']):.1f}%")
    c4.metric("Recall", f"{float(metrics['RECALL_PCT']):.1f}%")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Detection by attack pattern")
        pat = q(
            "SELECT t.PATTERN, s.RISK_BAND, COUNT(*) AS N FROM RECON.FRAUD_SCORES s "
            "JOIN RECON.FRAUD_TRUTH t ON t.TXN_ID = s.TXN_ID WHERE t.IS_FRAUD = 1 "
            "GROUP BY t.PATTERN, s.RISK_BAND"
        )
        st.bar_chart(pat.pivot_table(index="PATTERN", columns="RISK_BAND", values="N", fill_value=0))
        st.caption("Ground-truth labels are used only to measure accuracy, never for scoring.")
    with right:
        st.subheader("Alerts")
        min_score = st.slider("Minimum risk score", 0, 100, 60, step=5)
        alerts = q(
            "SELECT TXN_ID, CUSTOMER_ID, AMOUNT, CITY, TXN_TS, SCORE, RISK_BAND, REASONS "
            f"FROM RECON.FRAUD_SCORES WHERE SCORE >= {int(min_score)} "
            "ORDER BY SCORE DESC, AMOUNT DESC LIMIT 200"
        )
        st.dataframe(alerts, width="stretch", hide_index=True)

    st.subheader("Explain a transaction")
    default_id = int(alerts["TXN_ID"].iloc[0]) if len(alerts) else 1
    txn_id = st.number_input("TXN_ID", min_value=1, value=default_id, step=1)
    detail = q(
        "SELECT s.TXN_ID, s.SCORE, s.RISK_BAND, s.REASONS, f.CNT_10M, f.AMT_RATIO, "
        "f.DEV_SHARE, f.OFF_HOME, f.IS_FOREIGN, f.IS_NIGHT "
        "FROM RECON.FRAUD_SCORES s JOIN RECON.TXN_FEATURES f ON f.TXN_ID = s.TXN_ID "
        f"WHERE s.TXN_ID = {int(txn_id)}"
    )
    if len(detail):
        row = detail.iloc[0]
        st.write(f"**{row['RISK_BAND']}** (score {int(row['SCORE'])}): {row['REASONS'] or 'no risk signals'}")
        st.dataframe(detail.T.rename(columns={0: "value"}).astype(str), width="stretch")
    else:
        st.info("No such transaction.")