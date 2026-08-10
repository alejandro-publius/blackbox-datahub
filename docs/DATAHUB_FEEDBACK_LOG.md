# DataHub friction log (real observations during this build)

Kept for (a) the hackathon feedback survey, (b) candidate open-source contributions.
Everything below was actually hit on 2026-08-09 building BlackBox on macOS arm64 + colima.

## 1. Quickstart hangs silently with colima (docker contexts ignored) — HIGH VALUE
`datahub docker quickstart` uses docker-py's `docker.from_env()`, which honors `DOCKER_HOST`
but NOT docker CLI contexts. With colima (docker context = colima, no DOCKER_HOST), the CLI
printed "Starting up DataHub..." dots for 15+ minutes with zero real activity and no error.
Fix: `export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"`.
**Candidate contribution:** troubleshooting-docs addition (or a preflight check in
`docker_check.py` that detects a reachable `docker` CLI context while docker-py cannot
connect, and suggests DOCKER_HOST). Docs page: docs/troubleshooting/quickstart.

## 2. Stale docs: auth defaults & `--version head`
- Quickstart compose now ships `METADATA_SERVICE_AUTH_ENABLED: true` by default; several docs
  pages still say auth is disabled by default in quickstart → first GraphQL call 401s.
- One docs page still recommends `datahub docker quickstart --version head`; the floating
  `:head` tag was removed in v1.7.0.

## 3. `datahub init` default token duration is ONE_HOUR
Easy to mint a PAT that silently expires mid-session. A warning (or a more prominent
`--token-duration` mention in the quickstart auth docs) would save people.

## 4. MCP server mutation tools ambiguous for OSS Core
Docs say mutation tools are available in "mcp-server-datahub v0.5.0+ and DataHub Cloud
v0.3.17+" — unclear whether mutations work against self-hosted Core. We defaulted to
SDK/GraphQL for writes.

## 5. Docs claim a self-hosted MCP endpoint at `:8080/mcp`
agent-context docs mention `http://<gms-host>:8080/mcp`, but no MCP servlet appears to exist
in the OSS metadata-service; only the uvx stdio server is real for self-hosted.

## 6. Minor: Claude Code plugin install syntax
Docs show `claude plugins install datahub-skills --from github:...`; current Claude Code CLI
needs `claude plugin marketplace add datahub-project/datahub-skills` then
`claude plugin install datahub-skills@datahub-skills`.

## Positive notes (also feedback-worthy)
- SDK v2 (`datahub.sdk`) dataset + explicit `column_lineage=` mapping is excellent — table AND
  column lineage with attached transformation SQL in ~10 lines.
- Native incident entities (raiseIncident / updateIncidentStatus) working in OSS is a killer
  feature for agent writeback.
- `datahub datapack` UX is clean.
