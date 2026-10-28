import argparse
import os
import time

import numpy as np
import pandas as pd

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
          "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Indore", "Kochi"]
FOREIGN_CITIES = ["Lagos", "Dubai", "Singapore", "Moscow", "Kyiv", "Bucharest"]
CATEGORIES = ["grocery", "fuel", "dining", "electronics", "travel", "fashion",
              "utilities", "pharmacy", "entertainment", "online_marketplace"]
CHANNELS = ["POS", "ECOM", "UPI", "ATM"]
START = pd.Timestamp("2026-07-01")
DAYS = 90
HOUR_W = np.array([1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 8,
                   9, 8, 7, 7, 8, 9, 9, 8, 6, 4, 3, 2], dtype=float)
HOUR_W /= HOUR_W.sum()


def make_normal(rng, n, n_cust):
    cust = rng.integers(1, n_cust + 1, n)
    day = rng.integers(0, DAYS, n)
    hour = rng.choice(24, n, p=HOUR_W)
    sec = rng.integers(0, 3600, n)
    ts = START + pd.to_timedelta(day * 86400 + hour * 3600 + sec, unit="s")
    home_city = cust % len(CITIES)
    away = rng.random(n) < 0.04
    city_idx = np.where(away, rng.integers(0, len(CITIES), n), home_city)
    amount = np.round(np.clip(rng.lognormal(7.2, 1.0, n), 10, 150000), 2)
    return pd.DataFrame({
        "customer_id": cust,
        "device_id": cust * 10 + rng.integers(0, 2, n),
        "city": np.array(CITIES)[city_idx],
        "merchant_category": rng.choice(CATEGORIES, n),
        "channel": rng.choice(CHANNELS, n, p=[0.35, 0.30, 0.30, 0.05]),
        "amount": amount,
        "txn_ts": ts,
        "pattern": "normal",
    })


def make_fraud(rng, n_fraud, n_cust):
    frames = []
    n_a = int(n_fraud * 0.40)
    per_burst = 8
    bursts = max(n_a // per_burst, 1)
    cust = np.repeat(rng.integers(1, n_cust + 1, bursts), per_burst)
    base = np.repeat(rng.integers(0, DAYS * 86400, bursts), per_burst)
    off = rng.integers(0, 8 * 60, len(cust))
    frames.append(pd.DataFrame({
        "customer_id": cust,
        "device_id": cust * 10 + 9,
        "city": rng.choice(FOREIGN_CITIES, len(cust)),
        "merchant_category": rng.choice(["electronics", "online_marketplace"], len(cust)),
        "channel": "ECOM",
        "amount": np.round(rng.uniform(500, 5000, len(cust)), 2),
        "txn_ts": START + pd.to_timedelta(base + off, unit="s"),
        "pattern": "velocity_burst",
    }))

    n_b = int(n_fraud * 0.25)
    cust = rng.integers(1, n_cust + 1, n_b)
    day = rng.integers(0, DAYS, n_b)
    hour = rng.integers(1, 5, n_b)
    frames.append(pd.DataFrame({
        "customer_id": cust,
        "device_id": cust * 10 + rng.integers(0, 2, n_b),
        "city": np.array(CITIES)[cust % len(CITIES)],
        "merchant_category": rng.choice(["electronics", "travel", "fashion"], n_b),
        "channel": rng.choice(["ECOM", "POS"], n_b),
        "amount": np.round(rng.uniform(80000, 500000, n_b), 2),
        "txn_ts": START + pd.to_timedelta(day * 86400 + hour * 3600
                                          + rng.integers(0, 3600, n_b), unit="s"),
        "pattern": "amount_spike",
    }))

    n_c = n_fraud - n_a // per_burst * per_burst - n_b
    n_c = max(n_c, 1)
    cust = rng.integers(1, n_cust + 1, n_c)
    day = rng.integers(0, DAYS, n_c)
    hour = rng.integers(0, 5, n_c)
    frames.append(pd.DataFrame({
        "customer_id": cust,
        "device_id": cust * 10 + 9,
        "city": rng.choice(FOREIGN_CITIES, n_c),
        "merchant_category": rng.choice(CATEGORIES, n_c),
        "channel": rng.choice(["ECOM", "ATM"], n_c),
        "amount": np.round(rng.uniform(5000, 50000, n_c), 2),
        "txn_ts": START + pd.to_timedelta(day * 86400 + hour * 3600
                                          + rng.integers(0, 3600, n_c), unit="s"),
        "pattern": "account_takeover",
    }))
    return pd.concat(frames, ignore_index=True)


def build_bank(rng, ledger):
    n = len(ledger)
    s = rng.random(n)
    missing = s < 0.02
    fee_mismatch = (s >= 0.02) & (s < 0.05)
    ref_lost = (s >= 0.05) & (s < 0.075)

    bank = ledger.loc[~missing, ["txn_ref", "account_id", "amount", "txn_ts"]].copy()
    fm = fee_mismatch[~missing]
    rl = ref_lost[~missing]

    fee = np.round(rng.uniform(1, 50, fm.sum()), 2)
    bank.loc[fm, "amount"] = np.maximum(bank.loc[fm, "amount"].values - fee, 1.0).round(2)
    bank.loc[rl, "txn_ref"] = None

    delay = rng.choice([0, 1, 2], len(bank), p=[0.70, 0.25, 0.05])
    bank["value_date"] = (bank["txn_ts"].dt.normalize()
                          + pd.to_timedelta(delay, unit="D")).dt.strftime("%Y-%m-%d")
    bank = bank.drop(columns="txn_ts")

    dups = bank.sample(frac=0.01, random_state=int(rng.integers(0, 1_000_000)))
    bank = pd.concat([bank, dups], ignore_index=True)

    n_only = int(n * 0.015)
    max_acct = int(ledger["account_id"].max())
    only = pd.DataFrame({
        "txn_ref": None,
        "account_id": rng.integers(max_acct - 5000, max_acct + 1, n_only),
        "amount": np.round(np.clip(rng.lognormal(7.0, 1.0, n_only), 10, 100000), 2),
        "value_date": (START + pd.to_timedelta(rng.integers(0, DAYS, n_only), unit="D")
                       ).strftime("%Y-%m-%d"),
    })
    bank = pd.concat([bank, only], ignore_index=True)

    bank = bank.sample(frac=1.0, random_state=7).reset_index(drop=True)
    bank.insert(0, "bank_ref",
                "BNK" + pd.Series(np.arange(1, len(bank) + 1)).astype(str).str.zfill(9))
    return bank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fraud-rate", type=float, default=0.008)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()

    t0 = time.time()
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)

    n_fraud = int(a.rows * a.fraud_rate)
    n_normal = a.rows - n_fraud
    n_cust = max(a.rows // 20, 1000)

    df = pd.concat([make_normal(rng, n_normal, n_cust),
                    make_fraud(rng, n_fraud, n_cust)], ignore_index=True)
    df = df.sort_values("txn_ts", kind="stable").reset_index(drop=True)

    df.insert(0, "txn_id", np.arange(1, len(df) + 1))
    df.insert(1, "txn_ref", "TXN" + df["txn_id"].astype(str).str.zfill(9))
    df["account_id"] = 100_000_000 + df["customer_id"]
    df["currency"] = "INR"

    truth = df[["txn_id", "pattern"]].copy()
    truth["is_fraud"] = (truth["pattern"] != "normal").astype(int)

    ledger = df[["txn_id", "txn_ref", "customer_id", "account_id", "device_id",
                 "city", "merchant_category", "channel", "amount", "currency",
                 "txn_ts"]].copy()
    bank = build_bank(rng, ledger)

    ledger_out = ledger.copy()
    ledger_out["txn_ts"] = ledger_out["txn_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
    ledger_out.to_csv(os.path.join(a.out, "ledger.csv"), index=False)
    bank.to_csv(os.path.join(a.out, "bank_statement.csv"), index=False)
    truth.to_csv(os.path.join(a.out, "fraud_truth.csv"), index=False)

    print(f"ledger        : {len(ledger):>10,} rows")
    print(f"bank_statement: {len(bank):>10,} rows")
    print(f"fraud rows    : {int(truth['is_fraud'].sum()):>10,}")
    print(f"done in {time.time() - t0:.1f}s -> {a.out}/")


if __name__ == "__main__":
    main()