"""Build the BlackBox demo warehouse from data/sources CSVs.

Loads sources into DuckDB schema `raw`, runs SQL transforms into `staging`
and `marts`, and writes data/warehouse/metric_snapshot.json. Fully idempotent.
"""

import json
from pathlib import Path

import duckdb

TRANSFORM_ORDER = [
    "stg_orders.sql",
    "stg_customers.sql",
    "stg_fx_rates.sql",
    "fct_revenue.sql",
    "exec_revenue_metric.sql",
]

RAW_TABLES = {
    # table -> (csv file, explicit column types; raw stays close to the wire)
    "raw_orders": (
        "raw_orders.csv",
        {
            "order_id": "VARCHAR",
            "order_ts": "VARCHAR",
            "customer_id": "VARCHAR",
            "currency": "VARCHAR",
            "amount": "DOUBLE",
            "payment_processor": "VARCHAR",
            "status": "VARCHAR",
        },
    ),
    "raw_customers": (
        "raw_customers.csv",
        {
            "customer_id": "VARCHAR",
            "name": "VARCHAR",
            "segment": "VARCHAR",
            "country": "VARCHAR",
            "created_at": "VARCHAR",
        },
    ),
    "raw_fx_rates": (
        "raw_fx_rates.csv",
        {
            "rate_day": "VARCHAR",
            "currency": "VARCHAR",
            "usd_rate": "DOUBLE",
        },
    ),
}


def build(sources_dir: Path, warehouse_dir: Path) -> dict:
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    db_path = warehouse_dir / "blackbox.duckdb"
    # Idempotent: rebuild the warehouse file from scratch every run.
    db_path.unlink(missing_ok=True)
    (warehouse_dir / "blackbox.duckdb.wal").unlink(missing_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        con.execute("SET TimeZone = 'UTC'")
        for schema in ("raw", "staging", "marts"):
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        for table, (csv_name, columns) in RAW_TABLES.items():
            csv_path = sources_dir / csv_name
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"{csv_path} missing — run `uv run python pipeline/generate_sources.py --mode incident` first"
                )
            cols_sql = json.dumps(columns)
            con.execute(
                f"CREATE OR REPLACE TABLE raw.{table} AS "
                f"SELECT * FROM read_csv(?, header = true, columns = {cols_sql})",
                [str(csv_path)],
            )

        transforms_dir = Path(__file__).resolve().parent / "transforms"
        for name in TRANSFORM_ORDER:
            con.execute((transforms_dir / name).read_text())

        metric = con.execute(
            "SELECT kpi_day, revenue, trailing_28d_median_revenue, anomaly_ratio "
            "FROM marts.exec_revenue_metric"
        ).fetchone()
        daily = con.execute(
            "SELECT day, revenue_usd, order_count, aov_median_usd "
            "FROM marts.fct_revenue ORDER BY day"
        ).fetchall()
    finally:
        con.close()

    snapshot = {
        "kpi_day": str(metric[0]),
        "revenue": float(metric[1]),
        "expected_revenue": float(metric[2]),
        "anomaly_ratio": float(metric[3]),
        "daily": [
            {
                "day": str(d),
                "revenue_usd": float(rev),
                "order_count": int(cnt),
                "aov_median_usd": float(aov),
            }
            for d, rev, cnt, aov in daily
        ],
    }
    (warehouse_dir / "metric_snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    return snapshot


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    snap = build(repo_root / "data" / "sources", repo_root / "data" / "warehouse")
    print(
        f"built warehouse: kpi_day={snap['kpi_day']} revenue={snap['revenue']:.2f} "
        f"expected={snap['expected_revenue']:.2f} anomaly_ratio={snap['anomaly_ratio']:.2f} "
        f"({len(snap['daily'])} days)"
    )


if __name__ == "__main__":
    main()
