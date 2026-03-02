#!/usr/bin/env python3
"""
Generates init_us.sql and init_eu.sql with 1200 rows each.
Run: python seeds/generate_seeds.py
"""
import random
import math
import os

random.seed(42)

SCHEMA = """
-- Properties table
CREATE TABLE IF NOT EXISTS properties (
    id           BIGINT      PRIMARY KEY,
    price        DECIMAL(12,2) NOT NULL,
    bedrooms     INTEGER,
    bathrooms    INTEGER,
    region_origin VARCHAR(2)  NOT NULL,
    version      INTEGER     NOT NULL DEFAULT 1,
    updated_at   TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- Idempotency store
CREATE TABLE IF NOT EXISTS processed_requests (
    request_id    TEXT        PRIMARY KEY,
    response_body TEXT        NOT NULL,
    created_at    TIMESTAMP   NOT NULL DEFAULT NOW()
);
"""

def gen_price(base, variance=0.4):
    factor = 1 + (random.random() - 0.5) * variance * 2
    return round(base * factor, 2)

def make_rows(region, n=1200):
    rows = []
    base_id = 1 if region == "us" else 10001
    price_bases = [150000, 250000, 350000, 500000, 750000, 1200000]
    for i in range(n):
        pid = base_id + i
        price = gen_price(random.choice(price_bases))
        beds = random.choice([1, 2, 2, 3, 3, 3, 4, 4, 5])
        baths = random.choice([1, 1, 2, 2, 2, 3, 3, 4])
        rows.append((pid, price, beds, baths, region))
    return rows

def write_sql(region, rows, outdir):
    path = os.path.join(outdir, f"init_{region}.sql")
    with open(path, "w") as f:
        f.write(SCHEMA)
        f.write("\nINSERT INTO properties (id, price, bedrooms, bathrooms, region_origin) VALUES\n")
        parts = []
        for (pid, price, beds, baths, reg) in rows:
            parts.append(f"  ({pid}, {price}, {beds}, {baths}, '{reg}')")
        f.write(",\n".join(parts))
        f.write("\nON CONFLICT (id) DO NOTHING;\n")
    print(f"Wrote {path} ({len(rows)} rows)")

if __name__ == "__main__":
    outdir = os.path.dirname(os.path.abspath(__file__))
    for region in ("us", "eu"):
        rows = make_rows(region)
        write_sql(region, rows, outdir)
    print("Done.")
