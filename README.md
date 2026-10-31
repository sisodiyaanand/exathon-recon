# Real-Time Transaction Reconciliation & Fraud Risk Detector

**ExaThon India 2026 · Track 01: Money, Risk & Regulation** · Built on **Exasol Personal**

One explainable, set-based SQL pipeline that (1) reconciles a 1,000,000-transaction ledger against a 1,004,664-row bank statement and (2) scores every transaction for fraud risk, entirely inside Exasol.

- Pitch deck: [`docs/ExaThon_Deck.pdf`](docs/ExaThon_Deck.pdf)
- Demo video (3 min): https://drive.google.com/file/d/1GtoUnzQwNzWpCe8DvYPsLVYpY_YN8vsw/view?usp=sharing
- Backup copy of the demo video: [`docs/ExaThon_Demo_Final.mp4`](docs/ExaThon_Demo_Final.mp4)
- License: MIT

---

## 1. Problem statement

**Who has the problem:** banks, NBFCs, fintechs and payment gateways whose finance and risk teams reconcile ledger entries against bank statements.

**The problem:** reconciliation cycles never fully close. Matching is manual or spreadsheet-based and takes days; mismatches, missing entries and duplicate postings quietly hide real money. Fraud (velocity bursts, account takeover, amount spikes) is typically found after settlement, when the loss has already happened.

**Why it matters:** unresolved breaks tie up working capital and create compliance exposure, while late fraud detection is a direct financial loss.

**Our answer:** run both jobs as one SQL pipeline inside an analytical database, so matching and scoring over a million rows takes a single set-based pass, and every alert carries human-readable reasons.

## 2. Solution overview

```
 ledger.csv (1.00M)  ──┐
                       ├─►  Exasol Personal  ─►  02_reconcile.sql ─►  RECON_RESULT, RECON_SUMMARY
 bank_statement.csv ───┘   (schema RECON)    ─►  03_fraud.sql     ─►  TXN_FEATURES, FRAUD_SCORES, FRAUD_METRICS
 (1,004,664 rows)
```

**Reconciliation (`sql/02_reconcile.sql`)**
1. *Reference match* on `TXN_REF`; classify `MATCHED` vs `AMOUNT_MISMATCH`; duplicate bank postings ranked with `ROW_NUMBER()`.
2. *Fuzzy match* where the bank reference is missing: same account + same amount + value date within 2 days, one-to-one via bidirectional ranking.
3. *Exceptions:* `MISSING_IN_BANK`, `UNMATCHED_BANK`, `DUPLICATE_POSTING`.

**Fraud scoring (`sql/03_fraud.sql`)**
Features computed in SQL: transactions per customer in a 10-minute window (self-join), amount relative to the customer's own mean, off-home / foreign city, device rarity, night-time high value. An additive score (0-100) maps to `HIGH` (>=60), `MEDIUM` (>=35), `LOW`, and a `REASONS` column explains each flag. `FRAUD_METRICS` compares the HIGH band to ground-truth labels.

## 3. Why Exasol Personal

- 1,000,000 ledger rows bulk-loaded in about 2 seconds (`src/load_fast.py`).
- Large self-joins and window functions over 1M rows run in-database, with no dataframes or ETL framework in the matching path.
- Whole pipeline is plain SQL, reproducible in four commands.

## 4. Results

Synthetic data: 1,000,000 ledger transactions, 1,004,664 bank rows, 8,000 injected fraud cases. Full output in [`results.txt`](results.txt).

| Reconciliation status | Count | Value (base currency) |
|---|---:|---:|
| Matched (reference) | 924,812 | - |
| Matched (fuzzy: account + amount + date) | 24,918 | - |
| Amount mismatch | 30,135 | 0.77M variance |
| Missing in bank | 20,135 | 57.3M |
| Duplicate posting | 9,559 | 26.5M |
| Unmatched bank | 15,240 | 27.5M |

| Fraud pattern | Injected | Caught (HIGH) | Recall |
|---|---:|---:|---:|
| Account takeover | 2,800 | 2,800 | 100.0% |
| Amount spike | 2,000 | 1,966 | 98.3% |
| Velocity burst | 3,200 | 3,038 | 94.9% |
| **Overall** | 8,000 | 7,804 | **97.6%** |

HIGH band: **precision 98.8%**, recall 97.6% (TP 7,804 / FP 94 / FN 196); 7,898 of 1,000,000 transactions (0.79%) flagged.

> **Important:** data and fraud labels are synthetic and were injected by us, and the scoring thresholds were designed knowing those patterns (no held-out split). These numbers are a controlled benchmark, not evidence of real-world accuracy.

## 5. Setup and run guide

### Prerequisites
- Windows, macOS or Linux; Python 3.10+
- **Exasol Personal** launcher (`exasol` binary): https://github.com/exasol/exasol-personal
- For the `local` preset, Exasol Personal runs the database in a **Podman** container/VM (the launcher starts the Podman machine for you).

### Step 1: start Exasol Personal
```bash
exasol install local
exasol status        # expect: Status: database_ready
```
Connection details: host `127.0.0.1`, port `8563`, user `sys`, certificate validation disabled (self-signed). The password is stored by the launcher in `~/.exasol/personal/deployments/default/secrets.json`; the scripts read it automatically, so no password is kept in this repo.

### Step 2: install Python dependencies
```bash
git clone https://github.com/sisodiyaanand/exathon-recon.git
cd exathon-recon
python -m venv venv
# Windows: venv\Scripts\activate      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: generate the synthetic data
```bash
python src/generate_data.py      # writes data/ledger.csv, data/bank_statement.csv, data/fraud_truth.csv
```

### Step 4: load into Exasol, run the SQL pipeline, print results
```bash
python src/load_fast.py                                        # schema + CSV import (~seconds)
python src/run_sql.py sql/02_reconcile.sql sql/03_fraud.sql    # reconciliation + fraud scoring
python src/show_results.py                                     # summary, metrics, top-10 alerts
```

### Explore interactively
```bash
exasol connect
```
```sql
SELECT * FROM RECON.RECON_SUMMARY ORDER BY TXN_CNT DESC;
SELECT * FROM RECON.FRAUD_METRICS;
SELECT TXN_ID, AMOUNT, CITY, SCORE, REASONS FROM RECON.FRAUD_SCORES ORDER BY SCORE DESC LIMIT 10;
```

### Optional
`src/run_pipeline.py` and `src/app.py` (a pandas/Streamlit variant and dashboard) are optional and not needed for the pipeline above.

## 6. Repository structure

```
sql/01_schema.sql      schema RECON + tables + city dimension
sql/02_reconcile.sql   reference / fuzzy matching, exceptions, RECON_SUMMARY view
sql/03_fraud.sql       features, FRAUD_SCORES, FRAUD_METRICS view
src/generate_data.py   synthetic data generator with injected fraud episodes
src/load_fast.py       schema creation + CSV import via pyexasol
src/run_sql.py         runs one or more .sql files against Exasol
src/show_results.py    prints reconciliation and fraud results
results.txt            captured output of show_results.py
docs/                  pitch deck (PDF)
```

## 7. Data sources and licence

- **All data is synthetic**, generated by `src/generate_data.py`. No employer, customer or proprietary data is used.
- Code: **MIT License** (see `LICENSE`).

## 8. Tools and third-party components

- Exasol Personal (database), Podman (local container runtime used by Exasol Personal)
- Python, `pyexasol` (connection and CSV import); `pandas`, `faker` (data generation); `streamlit` (optional dashboard)
- No external APIs, and no LLM is called at runtime. Development was assisted by an AI model (Claude).

## 9. Limitations and future work

- Synthetic data and labels; thresholds not tuned on a held-out set; three fraud typologies only; rule-based scoring.
- Next: validate on anonymized real payment data, calibrate thresholds on train/validation splits, compare in-database ML, audit the foreign-location rule for geographic bias, add streaming ingestion.

## Author

Anand Sisodiya, M.S. Computer Science (Machine Learning), Georgia Institute of Technology; MBA, MANIT Bhopal.
