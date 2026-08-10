# Skill validation: `datahub-incident-investigation`

Real execution log for the skill contributed upstream to
[`datahub-project/datahub-skills`](https://github.com/datahub-project/datahub-skills).
Every command in the skill's `SKILL.md` and `references/investigation-recipes-reference.md`
was run against a live DataHub instance before the PR was opened; the outputs below are
verbatim (trimmed for length), not reconstructed.

**Nothing in the upstream skill references this repository.** The examples there are
vendor-neutral by design. This file is the local proof that the recipes actually execute.

## Environment

| Item              | Value                                            |
| ----------------- | ------------------------------------------------ |
| Date              | 2026-08-10                                       |
| DataHub GMS       | `http://localhost:8080` (quickstart)             |
| Deployment tier   | OSS — `serverEnv: core`, `serverType: quickstart` |
| CLI               | `acryl-datahub 1.7.0`                            |
| Auth              | `DATAHUB_GMS_TOKEN` from `.env` (never printed)  |
| Datasets exercised | 8 datasets on platform `duckdb`                 |

```bash
$ datahub -C skill=datahub-incident-investigation check server-config
{'datahub': {'serverEnv': 'core', 'serverType': 'quickstart'}, ...}
```

---

## Step 1 — Frame the symptom: estate health scan

```bash
datahub -C skill=datahub-incident-investigation search "*" \
  --where "hasActiveIncidents = true OR hasFailingAssertions = true" \
  --projection "urn type ... on Dataset { properties { name } platform { name }
    health { type status message } }" \
  --format json --limit 20
```

```json
{
  "total": 3,
  "searchResults": [
    {
      "entity": {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.fct_revenue,PROD)",
        "properties": { "name": "marts.fct_revenue" },
        "platform": { "name": "duckdb" },
        "health": [{ "type": "INCIDENTS", "status": "FAIL", "message": "2 active incidents" }]
      }
    },
    { "entity": { "properties": { "name": "raw.raw_orders" } } },
    { "entity": { "properties": { "name": "staging.stg_orders" } } }
  ]
}
```

**Finding that changed the skill:** `health` comes back as a **list** of health entries (one per
health type), not a single object. The skill and the recipes reference both say so explicitly
so an agent does not try to read `health.status`.

---

## Step 2 — Retrieve the contract

```bash
datahub -C skill=datahub-incident-investigation graphql --query /tmp/context.graphql --format json
```

```json
{
  "dataset": {
    "urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.fct_revenue,PROD)",
    "properties": {
      "name": "marts.fct_revenue",
      "description": null,
      "customProperties": [
        { "key": "pipeline", "value": "blackbox-demo-retail" },
        { "key": "build_tool", "value": "pipeline/run.py (DuckDB)" }
      ]
    },
    "editableProperties": {
      "description": "Daily revenue fact, USD-normalized. Grain: one row per day."
    },
    "ownership": {
      "owners": [
        {
          "owner": { "urn": "urn:li:corpuser:priya.desai" },
          "ownershipType": { "urn": "urn:li:ownershipType:__system__technical_owner" }
        }
      ]
    },
    "schemaMetadata": {
      "fields": [
        { "fieldPath": "day", "type": "DATE", "description": "Revenue date (UTC)." },
        { "fieldPath": "order_count", "type": "NUMBER", "description": "Completed orders that day." },
        {
          "fieldPath": "revenue_usd",
          "type": "NUMBER",
          "description": "Sum of USD-normalized order amounts. Feeds the Executive Revenue KPI."
        }
      ]
    },
    "health": [{ "type": "INCIDENTS", "status": "FAIL", "message": "1 active incident" }]
  }
}
```

**Finding that changed the skill:** `properties.description` was `null` while
`editableProperties.description` carried the actual contract. An agent that queries only one
of the two will wrongly report the field as undocumented. Both the SKILL and the recipes
reference now call this out as a gotcha.

---

## Step 3 — Localize with lineage

```bash
datahub -C skill=datahub-incident-investigation lineage \
  --urn "urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.exec_revenue_metric,PROD)" \
  --direction upstream --hops 3
```

```text
Upstream lineage: 5 entities, up to 3 hops

Hop   Type       Platform   Name                        URN
1     DATASET    duckdb     marts.fct_revenue           urn:li:dataset:(...,marts.fct_revenue,PROD)
2     DATASET    duckdb     staging.stg_fx_rates        urn:li:dataset:(...,staging.stg_fx_rates,PROD)
2     DATASET    duckdb     staging.stg_orders          urn:li:dataset:(...,staging.stg_orders,PROD)
3     DATASET    duckdb     raw.raw_fx_rates            urn:li:dataset:(...,raw.raw_fx_rates,PROD)
3     DATASET    duckdb     raw.raw_orders              urn:li:dataset:(...,raw.raw_orders,PROD)
```

Column-level narrowing (the step that shrinks the suspect set):

```bash
datahub -C skill=datahub-incident-investigation lineage \
  --urn "urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.fct_revenue,PROD)" \
  --column revenue_usd --direction upstream --hops 2
```

```text
Upstream lineage: 4 entities, up to 2 hops (showing 2 hops, increase --hops to see more)
1  DATASET  duckdb  staging.stg_fx_rates
1  DATASET  duckdb  staging.stg_orders
2  DATASET  duckdb  raw.raw_fx_rates
2  DATASET  duckdb  raw.raw_orders
```

Downstream blast radius:

```bash
datahub -C skill=datahub-incident-investigation lineage \
  --urn "urn:li:dataset:(urn:li:dataPlatform:duckdb,staging.stg_orders,PROD)" \
  --direction downstream --hops 3
```

```text
Downstream lineage: 2 entities, up to 2 hops
1  DATASET  duckdb  marts.fct_revenue
2  DATASET  duckdb  marts.exec_revenue_metric
```

Path confirmation:

```bash
datahub -C skill=datahub-incident-investigation lineage path \
  --from "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)" \
  --to "urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.exec_revenue_metric,PROD)"
```

```text
Path found (3 hops):
3  DATASET  duckdb  marts.exec_revenue_metric
```

Batch enrichment of the frontier (one call, not N):

```bash
datahub -C skill=datahub-incident-investigation search "*" \
  --where 'urn IN ("urn:li:dataset:(urn:li:dataPlatform:duckdb,staging.stg_orders,PROD)",
                   "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)")' \
  --projection "urn ... on Dataset { properties { name }
    ownership { owners { owner { ... on CorpUser { urn } } } }
    health { type status message } }" \
  --format json --limit 50
```

```json
{
  "total": 2,
  "searchResults": [
    {
      "entity": {
        "properties": { "name": "raw.raw_orders" },
        "ownership": { "owners": [{ "owner": { "urn": "urn:li:corpuser:jordan.lee" } }] },
        "health": [{ "type": "INCIDENTS", "status": "FAIL" }]
      }
    },
    {
      "entity": {
        "properties": { "name": "staging.stg_orders" },
        "ownership": { "owners": [{ "owner": { "urn": "urn:li:corpuser:priya.desai" } }] },
        "health": [{ "type": "INCIDENTS", "status": "FAIL" }]
      }
    }
  ]
}
```

Confirms the `urn IN (...)` passthrough filter works and returns owners + health in one round
trip — the pattern the skill recommends instead of per-entity fetches.

---

## Step 4/5 — Date the change

```bash
datahub -C skill=datahub-incident-investigation timeline \
  --urn "urn:li:dataset:(urn:li:dataPlatform:duckdb,staging.stg_orders,PROD)" \
  --category technical_schema
```

```text
2026-08-09 22:40:08 - 0.0.0-computed
  ADD TECHNICAL_SCHEMA dataset:duckdb:staging.stg_orders (field:amount): A forwards & backwards
    compatible change due to the newly added field 'amount'.
  ADD TECHNICAL_SCHEMA dataset:duckdb:staging.stg_orders (field:currency): ...
  ADD TECHNICAL_SCHEMA dataset:duckdb:staging.stg_orders (field:payment_processor): ...
```

Confirms the timestamp + compatibility classification the skill relies on for onset alignment.

---

## Step 6 — Read existing quality signals

```bash
datahub -C skill=datahub-incident-investigation graphql --query /tmp/health.graphql --format json
```

```text
assertions.total = 0
incidents.total  = 16
{
  "urn": "urn:li:incident:5d96b6ca-883c-4b60-8f8b-adf06f9f1401",
  "incidentType": "OPERATIONAL",
  "priority": "CRITICAL",
  "incidentStatus": { "state": "ACTIVE", "stage": "INVESTIGATION", "message": "..." }
}
```

Both `incidentStatus { ... }` (the spelling already used elsewhere in the upstream repo) and
`status { ... }` resolve on this server; the skill uses `incidentStatus` for consistency with
the existing `datahub-quality` docs.

**Finding that changed the skill:** there is **no top-level `incident(urn: ...)` query** on OSS.

```bash
datahub ... graphql --query 'query { incident(urn: "urn:li:incident:...") { urn } }'
```

```json
{
  "error": "graphql_error",
  "message": "Validation error (FieldUndefined@[incident]) : Field 'incident' in type 'Query' is undefined"
}
```

The recipes reference documents this and gives the two working alternatives (the owning
entity's `incidents(...)` connection, or `datahub get --urn <incident-urn>`).

Also note `assertions.total = 0` on a dataset with 16 active incidents — the concrete case for
the skill's claim that **absence of an assertion signal is not evidence of correctness**.

---

## Step 9 — Writeback loop (raise → resolve → verify → clean up)

The upstream `datahub-quality` skill marks `raiseIncident` / `updateIncidentStatus` as
Cloud-only. **Both work on OSS `serverEnv: core`.** Verified end to end on a throwaway
incident, then hard-deleted so the demo state was left untouched.

```bash
datahub -C skill=datahub-incident-investigation graphql --query /tmp/raise.graphql --format json
```

```json
{ "raiseIncident": "urn:li:incident:999b6235-3b2c-4153-80e1-ab9c8f96ab64" }
```

```bash
datahub -C skill=datahub-incident-investigation graphql --query 'mutation {
  updateIncidentStatus(urn: "urn:li:incident:999b6235-...", input: {
    state: RESOLVED, stage: FIXED,
    message: "Root cause: validated writeback path. Remediation verified; closing."
  })
}' --format json
```

```json
{ "updateIncidentStatus": true }
```

Verification via the aspect fetch the recipes recommend:

```bash
datahub -C skill=datahub-incident-investigation get --urn "urn:li:incident:999b6235-..."
```

```json
{
  "incidentInfo": {
    "entities": ["urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_customers,PROD)"],
    "priority": 3,
    "source": { "type": "MANUAL" },
    "status": {
      "state": "RESOLVED",
      "stage": "FIXED",
      "message": "Root cause: validated writeback path. Remediation verified; closing."
    },
    "type": "OPERATIONAL"
  },
  "incidentKey": { "id": "999b6235-3b2c-4153-80e1-ab9c8f96ab64" }
}
```

RCA link attachment (institutional memory), and its inverse:

```bash
datahub ... graphql --query 'mutation { addLink(input: {
  linkUrl: "https://example.internal/postmortems/INC-VALIDATION",
  label: "RCA: skill validation",
  resourceUrn: "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_customers,PROD)" }) }'
```

```json
{ "addLink": true }
```

```json
{ "removeLink": true }
```

Cleanup — the validation incident was hard-deleted, so no demo state was left behind:

```bash
datahub -C skill=datahub-incident-investigation delete --urn "urn:li:incident:999b6235-..." --hard -f
# Hard deleted 1 entities (impacts 3 versioned rows and 0 timeseries aspect rows) in 0.07 seconds.
```

---

## Summary of skill changes driven by live execution

| Observation from the live run                                     | Change made to the contributed skill                                     |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `health` is a list, not an object                                  | Stated explicitly in the recipes reference                               |
| `properties.description` null, `editableProperties.description` set | "Two description fields" gotcha in SKILL.md Step 2 and the recipes       |
| No top-level `incident(urn:)` query on OSS                         | Documented with the `FieldUndefined` error and two working alternatives  |
| `raiseIncident` / `updateIncidentStatus` / `addLink` work on OSS   | Writeback section states "verified against OSS (`serverEnv: core`)"      |
| `datahub lineage` does not accept `--projection`                   | Batch-enrich-via-search recipe added instead of per-entity fetches       |
| 16 active incidents with 0 assertions on the same dataset          | Used as the concrete case for "no failing assertion ≠ healthy"           |

## Lint gate

Run in the fork before pushing:

```text
trim trailing whitespace ....... Passed      check for broken symlinks ..... Passed
fix end of files ............... Passed      detect private key ............ Passed
check yaml ..................... Passed      check vcs permalinks .......... Passed
ruff / ruff-format ............. Passed
prettier (markdown) ............ All matched files use Prettier code style!
markdownlint-cli2 v0.21.0 ...... 167 files, 0 error(s)
```
