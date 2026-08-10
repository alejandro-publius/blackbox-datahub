# BlackBox — demo data stack targets
UV := uv run

.PHONY: setup demo-reset demo-healthy build test baselines

setup:
	uv sync

demo-reset:
	$(UV) python pipeline/generate_sources.py --mode incident
	$(UV) python pipeline/run.py

demo-healthy:
	$(UV) python pipeline/generate_sources.py --mode healthy
	$(UV) python pipeline/run.py

build:
	$(UV) python pipeline/run.py

test:
	$(UV) pytest pipeline/invariants -v

baselines:
	$(UV) python pipeline/make_baselines.py

# demo-run defined later
