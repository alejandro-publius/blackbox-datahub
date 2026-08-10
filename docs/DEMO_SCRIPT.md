# BlackBox — Demo Video Script (< 3:00)

Target runtime: **2:55** (hard limit is *under* 3:00 — Devpost rule). Narration budget ≈ 140 words/min; each segment's word count is annotated and pre-counted. Record narration separately if needed and cut video to it.

---

## Pre-flight checklist (do a full dry run first)

1. **DataHub OSS up** — `datahub docker quickstart`; UI at `http://localhost:9002`, GMS at `:8080`.
2. **Reset the demo** — `make demo-reset` (seeds incident fixture + rebuilds warehouse), then ensure metadata is synced: `uv run python -m blackbox.datahub.ingest`. (Alternatively `curl -X POST localhost:8400/api/demo/reset` once the backend is up — it does all of this including the DataHub re-sync.)
3. **Backend** — `.env` has `ANTHROPIC_API_KEY`; run `uv run uvicorn blackbox.api:app --port 8400 --app-dir backend`. Verify `curl localhost:8400/api/health` shows `warehouse_ready: true`, `datahub_connected: true`, `anthropic_configured: true`.
4. **Frontend** — `cd frontend && npm run dev`; open `http://localhost:3000`.
5. **Browser tabs prepared:**
   - Tab 1: BlackBox command center (`localhost:3000`).
   - Tab 2: DataHub UI, logged in (`datahub`/`datahub`), on `raw.raw_orders` — this is where the incident, remediation note and tag land. Dismiss the first-run product tour modal *before* recording. Refresh only when scripted.
   - No terminal needed on screen: the incident is filed from the UI's **Investigate Incident** dialog (prefilled report text).
6. **Recording:** 1080p or higher, hide bookmarks/notifications, dark OS theme to match the UI. Clean git state (`git status`), no leftover `blackbox/fix-*` branches.
7. **Timing reality check:** the live investigation takes ~2–5 minutes of wall clock. Record it in full, then **speed up the investigation and repair segments** to fit; add a small "footage sped up" caption during accelerated sections. Every result shown is still real.

---

## Script

### 0:00 – 0:15 — Hook (34 words)

**On screen:** BlackBox command center. KPI strip shows Executive Revenue **$2,737,323** vs expected **~$29,349** — anomaly badge **93.3x**. Slow zoom on the number.

**Narration:**
> Every data team has lived this morning: the executive revenue KPI is up ninety-three x, and nothing crashed. No errors, no alerts — just a wrong number. This is BlackBox: Sentry for your data stack.

### 0:15 – 0:35 — Report the incident (39 words)

**Clicks:** Click **Investigate Incident**. The dialog opens with the plain-English report prefilled: *"Revenue just jumped roughly 100x on the executive dashboard. Is this real?"* Click **Start Investigation**. The stage pill flips `REPORTED → CONTEXT_DISCOVERY`; first evidence cards appear.

**Narration:**
> I file one plain-English incident report — the kind an on-call human actually writes. BlackBox picks it up live: the stage pill flips to context discovery, and the agent's first move is not the data — it's DataHub, to learn what this KPI even means.

### 0:35 – 1:15 — Live DataHub-driven investigation (91 words; sped-up footage)

**Clicks:** Stay on Tab 1. Let the timeline fill: DataHub search → dataset context (contract docs) → lineage traversal (React Flow graph draws itself, nodes turn `investigating`/`suspicious`). Click the **Hypotheses** tab when the FX hypothesis flips to `eliminated`; hover the profile-by-`payment_processor` evidence card.

**Narration:**
> Watch the timeline. Every card is a real tool result: DataHub search finds the metric, its schema docs carry the data contract, and real column-level lineage draws this graph — no hardcoded topology. The agent quantifies the symptom against a committed healthy baseline: onset August seventh, ninety-three x. It registers hypotheses for every upstream branch. The FX feed looks suspicious — it went stale — but profiling shows a two-percent effect. Eliminated, with cited evidence. Then it profiles order amounts segmented by payment processor, straight from the lineage path, and one segment lights up.

### 1:15 – 1:40 — ROOT CAUSE CONFIRMED (53 words)

**On screen:** the `RootCauseCard` drawer slides up: summary sentence, blamed asset `raw.raw_orders`, field `amount`, cited evidence ids. Lineage graph: root-cause node red, downstream nodes marked `affected`.

**Narration:**
> Root cause confirmed: cloudpay_v2 orders report amounts in cents, not dollars, from the August seventh cutover — a semantic failure the schema can't catch. And here's the key: this confirmation is machine-validated. The system rejects any root cause that doesn't cite DataHub lineage plus quantitative evidence naming the blamed field. The agent cannot bluff.

### 1:40 – 2:10 — Repair & Verify (68 words; sped-up footage)

**Clicks:** Click **Repair & Verify** on the RootCauseCard. Stage pill: `REPAIR_GENERATED → REPAIR_TESTING → VERIFIED`. `ResolutionCard` appears: unified diff of `pipeline/transforms/stg_orders.sql`, test report **32/32 passed**, before/after KPI.

**Narration:**
> I authorize the repair — a human stays in the loop. The agent reads the staging transform and proposes a targeted fix: normalize cents to dollars only for post-cutover cloudpay_v2 rows. That's a real unified diff, applied to the real file. The warehouse rebuilds, and the full thirty-two-test invariant suite runs. All green — and the KPI recomputes back to one-point-oh. Verification is the gate; no green suite, no fix.

### 2:10 – 2:35 — The receipts, in DataHub itself (51 words)

**Clicks:** Point at the ResolutionCard's git line (`blackbox/fix-<id>` + commit). Switch to Tab 2 (DataHub UI) and refresh: show the dataset's **Documentation** tab with the appended **Incident history** note (root cause, patch file, branch/commit, 32/32 verification) and the **blackbox-remediated** tag in the sidebar.

> ⚠️ **Capture gotcha (learned in the drill):** DataHub's **Incidents** tab lists *ACTIVE* incidents only. Once BlackBox resolves the incident it disappears from that tab, so filming the Incidents tab *after* the repair shows an empty list. Either (a) film the Incidents tab during the investigation window — the incident is raised ACTIVE the moment the root cause is confirmed, and shows as `Critical (1) · [BlackBox] …` with 4 assets (see `docs/screenshots/05-datahub-incident.png`) — and then show the Documentation note after the repair, or (b) show only the Documentation note + tag here. Option (a) is the stronger story: raised → resolved.

**Narration:**
> The fix is committed to a real git branch. And here — in DataHub's own UI — is the writeback: a resolved incident on the affected datasets with the root cause and test results, a remediation note appended to the docs, and a blackbox-remediated tag. The context graph now remembers this outage forever.

### 2:35 – 2:55 — Architecture + why DataHub matters (47 words)

**On screen:** the architecture diagram from `docs/ARCHITECTURE.md` (one static slide), then cut back to the healthy KPI with the end card: "BlackBox — Autonomous Data Incident Response".

**Narration:**
> Under the hood: Claude drives strategy, but every fact comes from deterministic tools, and DataHub is the map — schemas, contracts, and lineage in; incidents, docs, and tags back out. The scenario is synthetic and disclosed; every number you saw was real execution. BlackBox — autonomous data incident response.

### 2:55 — End card, cut to black. Total narration: 383 words.

---

## Fallback notes

- If the live run stalls or exceeds `MAX_TURNS`, `POST /api/demo/reset` and re-record — the fixture is byte-identical every run.
- Keep at least one clean full recording before attempting stylistic retakes; the deadline is Aug 10, 5:00 PM ET.
- Do not include third-party trademarks or music (Devpost rule). DataHub's own UI shown for the writeback is the product being integrated with — that is the point of the category.
