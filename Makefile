# BlackBox — Autonomous Data Incident Response
UV := uv run

.PHONY: judge-check setup demo-reset demo-healthy build test baselines datahub-up datahub-setup ingest api frontend demo-run evals e2e

setup:
	uv sync
	cd frontend && npm install

## -- demo data stack ---------------------------------------------------------

demo-reset:
	git checkout -- pipeline/transforms/ 2>/dev/null || true
	rm -f pipeline/transforms/*.sql.orig
	$(UV) python pipeline/generate_sources.py --mode incident
	$(UV) python pipeline/run.py
	rm -f data/incidents/inc_*.json data/incidents/*.transcript.jsonl

demo-healthy:
	git checkout -- pipeline/transforms/ 2>/dev/null || true
	rm -f pipeline/transforms/*.sql.orig
	$(UV) python pipeline/generate_sources.py --mode healthy
	$(UV) python pipeline/run.py

build:
	$(UV) python pipeline/run.py

test:
	$(UV) pytest pipeline/invariants -v

baselines:
	$(UV) python pipeline/make_baselines.py

## -- DataHub -----------------------------------------------------------------

datahub-up:
	DOCKER_HOST=$${DOCKER_HOST:-unix://$$HOME/.colima/default/docker.sock} \
		datahub docker quickstart --version v1.7.0

# Mints a PAT, writes it to .env, ingests the pipeline metadata, verifies round-trip.
datahub-setup:
	bash scripts/setup_datahub.sh

ingest:
	$(UV) python -m blackbox.datahub.ingest

## -- services ----------------------------------------------------------------

api:
	$(UV) uvicorn blackbox.api:app --port 8400 --app-dir backend

frontend:
	cd frontend && npm run dev

# Start both services (Ctrl-C stops both). For the demo, run `make demo-reset` first.
demo-run:
	@trap 'kill 0' INT TERM; \
	$(UV) uvicorn blackbox.api:app --port 8400 --app-dir backend & \
	(cd frontend && npm run dev) & \
	wait

## -- verification -------------------------------------------------------------

# Deterministic, keyless proof path for judges — same evidence CI runs.
# No Anthropic key, no live DataHub, no remote. Restores the incident fixture.
judge-check:
	bash scripts/judge_check.sh

evals:
	$(UV) python -m evals.run_evals

e2e:
	cd frontend && npx playwright test
