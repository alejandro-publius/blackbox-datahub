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

## Script — 2:52 target

Total narration ≈ 400 words at ~140 wpm. The through-line is **proof → action → proof**: never show a claim without the receipt next to it.

### 0:00 – 0:15 — The stakes (36 words)

**On screen:** command center, Executive Revenue **$2,737,324** with the red **93× EXPECTED** badge; slow push in on the number.

> Every data team has lived this morning. Revenue is up ninety-three times. Nothing crashed, no job failed, no alert fired. The schema is still valid — the number is just wrong.

### 0:15 – 0:25 — One plain-English report (25 words)

**Clicks:** **Investigate Incident** → dialog prefilled *"Revenue just jumped roughly 100x on the executive dashboard. Is this real?"* → **Start Investigation**.

> That's the entire input. One sentence, the kind an on-call engineer actually writes. BlackBox takes it from there — autonomously.

### 0:25 – 0:45 — DataHub is the map (44 words)

**On screen:** timeline fills with `DATAHUB` badges; React Flow graph draws itself; nodes flip to *investigating*.

> Its first move isn't the data — it's DataHub. It searches the catalog through the official MCP server, reads the data contract on the field, and walks column-level lineage upstream from the KPI. It never guesses the topology.

### 0:45 – 0:55 — Competing hypotheses (23 words)

**Clicks:** **Hypotheses** tab.

> It doesn't chase one hunch. It opens competing hypotheses across every upstream branch — the order stream and the currency feed both suspects.

### 0:55 – 1:10 — Eliminating the distractor (34 words)

**On screen:** the FX hypothesis flips to **eliminated**; hover its cited evidence.

> The stale currency feed looks guilty and isn't. BlackBox kills it with arithmetic: rates moved under half a percent, two orders of magnitude too small to explain a hundred-x. Eliminated on evidence, not vibes.

### 1:10 – 1:20 — Root cause (26 words)

**On screen:** the **ROOT CAUSE CONFIRMED** card.

> `raw_orders.amount`. A payment provider cut over and started sending integer cents where the contract says dollars. Every order inflated exactly one hundred times.

### 1:20 – 1:35 — The gate (37 words)

**On screen:** hold on the cited evidence chips.

> Here's the part that matters. That conclusion had to pass a gate written in code, not prose: cite DataHub lineage evidence, and cite quantitative evidence naming that exact field. The agent cannot talk its way past it.

### 1:35 – 1:45 — The authority boundary (30 words)

**Clicks:** hover, then press **Repair & Verify**.

> Diagnosis is autonomous. Mutation is not: a human authorizes one constrained repair. If it fails verification BlackBox reverts it, and nothing reaches GitHub until the fix earns verified.

### 1:45 – 1:55 — Real code, really executed (23 words)

**On screen:** the unified diff in the resolution card.

> It writes the fix into the actual transform — provider-scoped, not a blanket divide — then rebuilds the warehouse for real.

### 1:55 – 2:10 — Verification (34 words)

**On screen:** **32/32 TESTS PASSED**; before/after KPI **$2,737,324 → $27,373**.

> Then it has to prove the repair. The full invariant suite: thirty-two of thirty-two. And the KPI lands within one percent of the committed healthy baseline.

### 2:10 – 2:18 — The bad repair we reject (25 words)

**On screen:** cut to `evals/results/latest.md`, the `bad_repair_rejected` row.

> We also test the opposite. A naive fix that restores the headline number while corrupting history gets rejected by the historical invariants.

### 2:18 – 2:30 — The engineering artifact (28 words)

**On screen:** the git row, then the real GitHub pull request.

> The verified fix lands as a real pull request — the diff, the evidence, the before-and-after, the test results. A reviewable artifact, not a chat log.

### 2:30 – 2:42 — DataHub remembers (28 words)

**On screen:** DataHub UI — the incident, then the remediation note and tag on the dataset.

> And the resolution goes back into DataHub: the incident resolved, the root cause written onto the asset. The next engineer inherits the investigation.

### 2:42 – 2:52 — The punchline (27 words)

**On screen:** architecture diagram, then the healthy KPI end card.

> Claude decides what to investigate. Deterministic tools decide what is true. DataHub is both the map it investigates with and the memory it leaves behind.

---

## Shot notes

- **DataHub Incidents tab lists ACTIVE only.** Film the incident during the investigation window (it's raised the moment the cause is proven — `docs/screenshots/05-datahub-incident.png`), then show the Documentation note after the repair. Filming that tab post-repair shows an empty list.
- **Speed up 0:25–1:10 and 1:42–1:55.** The live run is ~2-3 minutes; caption accelerated sections "footage sped up". Every number on screen stays real.
- **Optional 2-second inserts** if the cut runs short: the Phoenix trace (`07-phoenix-trace.png`) showing one incident as one trace, and the upstream PRs. Cut these first if long — they are depth, not story.
- **Do not** narrate the framework list. The judge should remember proof → action → proof.
