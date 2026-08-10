"""Emit the demo pipeline's metadata into DataHub OSS.

Honesty contract: every schema emitted here is INTROSPECTED from the real DuckDB
warehouse (so DataHub always mirrors reality), and lineage edges mirror the SQL
transforms that actually run — each edge carries the transform's real SQL as its
transformation text. Field documentation encodes the data contracts a real
payments/analytics org would maintain. Nothing references the seeded incident's
nature (that must be discovered from data, not metadata).

Run: uv run python -m blackbox.datahub.ingest
"""

from __future__ import annotations

import duckdb

from ..config import REPO_ROOT, settings

PLATFORM = "duckdb"
ENV = "PROD"

TABLES = [
    "raw.raw_orders",
    "raw.raw_customers",
    "raw.raw_fx_rates",
    "staging.stg_orders",
    "staging.stg_customers",
    "staging.stg_fx_rates",
    "marts.fct_revenue",
    "marts.exec_revenue_metric",
]

DATASET_DOCS: dict[str, str] = {
    "raw.raw_orders": (
        "Order events extracted nightly from the payments platform.\n\n"
        "**Contract (payments-platform, v1.3):** one row per order attempt; `amount` is a decimal "
        "in major currency units; `status` reflects the terminal state at extract time."
    ),
    "raw.raw_customers": "Customer master extract from CRM. One row per customer.",
    "raw.raw_fx_rates": (
        "Daily FX reference rates (per currency, vs USD) from the treasury feed. "
        "Expected to update every business day."
    ),
    "staging.stg_orders": (
        "Cleaned order stream. Excludes cancelled and refunded orders from the revenue path. "
        "This is the canonical input for all revenue reporting."
    ),
    "staging.stg_customers": "Typed customer dimension staging table.",
    "staging.stg_fx_rates": "FX rates with a full day spine (missing days forward-filled from the last known rate).",
    "marts.fct_revenue": "Daily revenue fact, USD-normalized. Grain: one row per day.",
    "marts.exec_revenue_metric": (
        "**Executive Revenue KPI** — the single number reported on the executive dashboard every "
        "morning. `anomaly_ratio` compares the latest day to a stable trailing-28d median window."
    ),
}

FIELD_DOCS: dict[str, dict[str, str]] = {
    "raw.raw_orders": {
        "order_id": "Globally unique order identifier (hex).",
        "order_ts": "Order capture timestamp, UTC ISO-8601.",
        "customer_id": "FK to raw_customers.customer_id.",
        "currency": "ISO-4217 currency code of the order (USD/EUR/GBP/CAD).",
        "amount": (
            "Order amount in MAJOR currency units as a decimal (e.g. 49.99 = $49.99). "
            "Contract v1.3: two decimal places, as reported by the capturing payment processor."
        ),
        "payment_processor": (
            "Payment provider that captured the order. Known values: legacy_pos, shopgate, "
            "cloudpay_v2 (provider migration began 2026-08-07 per payments-platform runbook)."
        ),
        "status": "Terminal order state: completed | cancelled | refunded.",
    },
    "raw.raw_fx_rates": {
        "rate_day": "Rate effective date.",
        "currency": "ISO-4217 code.",
        "usd_rate": "Units of USD per 1 unit of currency.",
    },
    "staging.stg_orders": {
        "amount": "Order amount in major currency units (passed through from raw_orders under contract v1.3).",
        "order_day": "Order date (UTC) derived from order_ts.",
        "payment_processor": "Capturing payment provider (see raw_orders.payment_processor).",
    },
    "marts.fct_revenue": {
        "day": "Revenue date (UTC).",
        "order_count": "Completed orders that day.",
        "revenue_usd": "Sum of USD-normalized order amounts. Feeds the Executive Revenue KPI.",
        "aov_usd": "Mean order value (USD).",
        "aov_median_usd": "Median order value (USD) — robust health signal for unit/semantic drift.",
    },
    "marts.exec_revenue_metric": {
        "kpi_day": "The day the KPI reports on (latest complete day).",
        "revenue": "Executive Revenue for kpi_day (USD).",
        "trailing_28d_median_revenue": "Median daily revenue over the stable trailing window (kpi_day-35 .. kpi_day-8).",
        "anomaly_ratio": "revenue / trailing_28d_median_revenue. Healthy ≈ 1.0.",
    },
}

# owner urns -> (display name, title, tables owned)
OWNERS = {
    "jordan.lee": ("Jordan Lee", "Staff Engineer, Payments Platform", ["raw.raw_orders", "raw.raw_customers", "raw.raw_fx_rates"]),
    "priya.desai": (
        "Priya Desai",
        "Analytics Engineering Lead",
        ["staging.stg_orders", "staging.stg_customers", "staging.stg_fx_rates", "marts.fct_revenue", "marts.exec_revenue_metric"],
    ),
}

TAGS = {
    "marts.exec_revenue_metric": ["kpi", "executive-reporting"],
    "marts.fct_revenue": ["revenue"],
}

# (upstream, downstream, transform file, {downstream_col: [upstream_cols]})
LINEAGE: list[tuple[str, str, str | None, dict[str, list[str]]]] = [
    (
        "raw.raw_orders", "staging.stg_orders", "stg_orders.sql",
        {
            "order_id": ["order_id"], "order_ts": ["order_ts"], "order_day": ["order_ts"],
            "customer_id": ["customer_id"], "currency": ["currency"], "amount": ["amount"],
            "payment_processor": ["payment_processor"], "status": ["status"],
        },
    ),
    (
        "raw.raw_customers", "staging.stg_customers", "stg_customers.sql",
        {c: [c] for c in ["customer_id", "name", "segment", "country", "created_at"]},
    ),
    (
        "raw.raw_fx_rates", "staging.stg_fx_rates", "stg_fx_rates.sql",
        {"rate_day": ["rate_day"], "currency": ["currency"], "usd_rate": ["usd_rate"]},
    ),
    (
        "staging.stg_orders", "marts.fct_revenue", "fct_revenue.sql",
        {
            "day": ["order_day"], "order_count": ["order_id"],
            "revenue_usd": ["amount", "currency"], "aov_usd": ["amount"], "aov_median_usd": ["amount"],
        },
    ),
    (
        "staging.stg_fx_rates", "marts.fct_revenue", "fct_revenue.sql",
        {"revenue_usd": ["usd_rate"], "aov_usd": ["usd_rate"], "aov_median_usd": ["usd_rate"]},
    ),
    (
        "marts.fct_revenue", "marts.exec_revenue_metric", "exec_revenue_metric.sql",
        {
            "kpi_day": ["day"], "revenue": ["revenue_usd"],
            "trailing_28d_median_revenue": ["revenue_usd"], "anomaly_ratio": ["revenue_usd"],
        },
    ),
]


def _introspect_schema(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str, str]]:
    docs = FIELD_DOCS.get(table, {})
    rows = con.sql(f"DESCRIBE {table}").fetchall()
    return [(name, dtype, docs.get(name, "")) for name, dtype, *_ in rows]


def dataset_urn(table: str) -> str:
    import datahub.emitter.mce_builder as builder

    return builder.make_dataset_urn(platform=PLATFORM, name=table, env=ENV)


def ingest() -> dict:
    from datahub.emitter.mcp import MetadataChangeProposalWrapper
    from datahub.metadata.urns import CorpUserUrn, DatasetUrn, TagUrn
    from datahub.sdk import DataHubClient, Dataset
    import datahub.metadata.schema_classes as models

    client = DataHubClient(
        server=settings.datahub_gms_url, token=settings.datahub_gms_token or None
    )

    con = duckdb.connect(str(settings.warehouse_path), read_only=True)
    table_owner = {t: user for user, (_, _, tables) in OWNERS.items() for t in tables}

    # corp users first so ownership renders nicely
    for user, (display, title, _tables) in OWNERS.items():
        client._graph.emit(
            MetadataChangeProposalWrapper(
                entityUrn=str(CorpUserUrn(user)),
                aspect=models.CorpUserInfoClass(
                    active=True, displayName=display, title=title, email=f"{user}@blackbox.demo"
                ),
            )
        )

    emitted = []
    for table in TABLES:
        ds = Dataset(
            platform=PLATFORM,
            name=table,
            env=ENV,
            description=DATASET_DOCS.get(table, ""),
            schema=_introspect_schema(con, table),
            custom_properties={
                "pipeline": "blackbox-demo-retail",
                "build_tool": "pipeline/run.py (DuckDB)",
                "note": "Deterministic demo fixture — synthetic data, real executable pipeline.",
            },
        )
        ds.add_owner(CorpUserUrn(table_owner[table]))
        for tag in TAGS.get(table, []):
            ds.add_tag(TagUrn(tag))
        client.entities.upsert(ds)
        emitted.append(table)

    edges = 0
    for up, down, transform_file, col_map in LINEAGE:
        sql_text = None
        if transform_file:
            p = settings.transforms_dir / transform_file
            if p.exists():
                sql_text = p.read_text()
        kwargs = dict(
            upstream=DatasetUrn(platform=PLATFORM, name=up, env=ENV),
            downstream=DatasetUrn(platform=PLATFORM, name=down, env=ENV),
            column_lineage=col_map,
        )
        if sql_text:
            kwargs["transformation_text"] = sql_text
        client.lineage.add_lineage(**kwargs)
        edges += 1

    con.close()
    return {"datasets": emitted, "lineage_edges": edges}


def verify() -> dict:
    """Round-trip check: search + lineage traversal + contract retrieval."""
    from . import client as read_client

    search_hits = read_client.search("executive revenue")
    metric_urn = dataset_urn("marts.exec_revenue_metric")
    lin = read_client.lineage(metric_urn, direction="UPSTREAM", max_hops=4)
    contract = read_client.get_dataset(dataset_urn("raw.raw_orders"))
    amount_doc = next(
        (f["description"] for f in contract["schema_fields"] if f["field"] == "amount"), None
    )
    return {
        "search_hits": len(search_hits),
        "lineage_nodes": len(lin["nodes"]),
        "lineage_edges": len(lin["edges"]),
        "column_mapped_edges": sum(1 for e in lin["edges"] if e["columns"]),
        "amount_contract_present": bool(amount_doc and "major currency units" in amount_doc.lower()),
    }


if __name__ == "__main__":
    print("Emitting demo pipeline metadata to DataHub at", settings.datahub_gms_url)
    print(ingest())
    print("Verifying round-trip …")
    print(verify())
