\## How to run (Windows)



```bat

exasol install local

python src\\generate\_data.py

python src\\load\_fast.py

python src\\run\_sql.py sql\\02\_reconcile.sql sql\\03\_fraud.sql

python src\\show\_results.py

```



`run\_pipeline.py` and `app.py` (pandas/Streamlit dashboard) are optional.



\## Results (synthetic data: 1,000,000 ledger txns, 1,004,664 bank rows, 8,000 injected fraud cases)



| Reconciliation status | Count |

|---|---|

| Matched (reference) | 924,812 |

| Matched (fuzzy: account+amount+date) | 24,918 |

| Amount mismatch | 30,135 |

| Missing in bank | 20,135 |

| Duplicate posting | 9,559 |

| Unmatched bank | 15,240 |



Fraud scoring (HIGH risk band): Precision 98.8%, Recall 97.6% (TP 7,804 / FP 94 / FN 196).

All matching and scoring logic runs inside Exasol SQL.



Note: data and fraud labels are synthetic, so these metrics reflect a controlled benchmark, not real-world accuracy.

Full output: `results.txt`.

