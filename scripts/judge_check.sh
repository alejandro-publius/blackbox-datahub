#!/usr/bin/env bash
# Deterministic, keyless proof path for judges — the same evidence CI runs.
#
# Needs NO Anthropic key, NO live DataHub, NO GitHub token, NO Phoenix, and no
# network beyond the package installs the project already requires. It never
# runs a live agent, never touches a git remote, never opens a PR, and restores
# the demo's incident fixture on the way out so the tree is left as it was found.
set -uo pipefail
cd "$(dirname "$0")/.."

pass=0; fail=0
declare -a LINES
step() { # step <label> <var-with-detail> <status>
  if [ "$3" = "PASS" ]; then pass=$((pass+1)); else fail=$((fail+1)); fi
  LINES+=("$(printf '%-22s %s — %s' "$1" "$3" "$2")")
}

echo "▸ BlackBox judge check — deterministic, no API key required"
echo

# ── 1. backend unit tests ───────────────────────────────────────────────────
# tests/ opens the warehouse read-only, so build the HEALTHY fixture first.
echo "① building the healthy fixture (deterministic, seed-pinned) …"
if uv run python pipeline/generate_sources.py --mode healthy >/dev/null 2>&1 \
   && uv run python pipeline/run.py >/dev/null 2>&1; then
  fixture_ok=1
else
  fixture_ok=0
fi

echo "② backend unit tests …"
# pyproject already sets addopts="-q", so an extra -q suppresses the summary
# line entirely. Count from the junit report instead of parsing prose.
if [ "$fixture_ok" = "1" ] \
   && out=$(uv run pytest tests/ -p no:warnings --junitxml=/tmp/bb-unit.xml 2>&1); then
  read -r u_total u_bad <<<"$(uv run python - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse("/tmp/bb-unit.xml").getroot()
s = r if r.tag == "testsuite" else r.find("testsuite")
print(int(s.get("tests",0)), int(s.get("failures",0))+int(s.get("errors",0)))
PY
)"
  step "backend:" "$u_total tests" PASS
else
  step "backend:" "see output below" FAIL
  printf '%s\n' "${out:-fixture build failed}" | tail -15
fi

# ── 2. invariants on the healthy fixture: must be exactly N/N ───────────────
echo "③ pipeline invariants on the healthy fixture …"
if [ "$fixture_ok" = "1" ] \
   && uv run pytest pipeline/invariants -q -p no:warnings --junitxml=/tmp/bb-inv.xml >/dev/null 2>&1; then
  read -r total bad skipped <<<"$(uv run python - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse("/tmp/bb-inv.xml").getroot()
s = r if r.tag == "testsuite" else r.find("testsuite")
print(int(s.get("tests",0)),
      int(s.get("failures",0))+int(s.get("errors",0)),
      int(s.get("skipped",0)))
PY
)"
  if [ "$bad" = "0" ] && [ "$skipped" = "0" ] && [ "$total" -gt 0 ]; then
    step "healthy pipeline:" "$total/$total" PASS
  else
    step "healthy pipeline:" "$((total-bad-skipped))/$total ($bad failing, $skipped skipped)" FAIL
  fi
else
  step "healthy pipeline:" "suite did not run clean" FAIL
fi

# ── 3. frontend lint + production build ─────────────────────────────────────
echo "④ frontend lint + production build …"
if [ -d frontend/node_modules ]; then
  if (cd frontend && npm run lint >/dev/null 2>&1 && npm run build >/dev/null 2>&1); then
    step "frontend lint/build:" "clean" PASS
  else
    step "frontend lint/build:" "failed — run 'cd frontend && npm run build'" FAIL
  fi
else
  step "frontend lint/build:" "SKIPPED — run 'cd frontend && npm install' first" FAIL
fi

# ── 4. no tracked secrets ───────────────────────────────────────────────────
echo "⑤ tracked-secret scan …"
hits=$(git ls-files -z \
  | xargs -0 grep -lE 'sk-ant-api03-[A-Za-z0-9_-]{40,}|-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}' \
    2>/dev/null | grep -v '^scripts/judge_check.sh$' || true)
env_tracked=$(git ls-files | grep -c '^\.env$' || true)
if [ -z "$hits" ] && [ "$env_tracked" = "0" ]; then
  step "secrets:" "none tracked, .env ignored" PASS
else
  step "secrets:" "FOUND: ${hits:-.env is tracked}" FAIL
fi

# ── restore the demo's ground state (incident fixture) ──────────────────────
echo "⑥ restoring the incident fixture …"
uv run python pipeline/generate_sources.py --mode incident >/dev/null 2>&1
uv run python pipeline/run.py >/dev/null 2>&1

echo
echo "BLACKBOX JUDGE CHECK"
printf '%s\n' "${LINES[@]}"
echo "No API key, live DataHub, GitHub token or Phoenix used. No remote touched."
echo

if [ "$fail" -gt 0 ]; then
  echo "✗ $fail check(s) failed."
  exit 1
fi
echo "✓ all $pass checks passed."
