# mcp-ogc — Developer Handoff & Project State

> **Read this first.** This file is the living source of truth for anyone (human or AI agent)
> picking up `mcp-ogc` cold. Keep it updated as the project moves. If you finish a task or make
> a decision that future-you would want to know, write it here.

---

## What this project is (in one paragraph)

`mcp-ogc` is an **MCP (Model Context Protocol) server** that lets LLM agents query geospatial
data. It translates between an AI client (Claude, etc.) and **OGC** geodata services — **WMS**
(map images) and **WFS** (vector features as GeoJSON). It wraps the `owslib` library and exposes
three tools an agent can call. Think: "give an AI the ability to fetch maps and geographic data
from any standards-compliant government GIS server."

## Why it exists (the real driver)

It's evidence for a procurement bid. **Foursight Lab** is applying to *Govtech4all Pilot 3*
(Sundsvalls kommun, ref UH-2026-159). A scored criterion rewards demonstrable open-source work.
Publishing this AGPL-3.0 repo before the bid turns a promise into proof. **Hard deadline: the repo
must be public and tagged `v0.1.0` by 2026-06-03 EOD.** Bid submission deadline is 2026-06-05.

Consequence: the repo must look like **real, careful work** (clean commits, tests, CI, a demo —
not application theater) and be **genuinely useful to others**, not just Sundsvall.

---

## Current status

**As of 2026-05-29: Days 1–4 complete.** Repo is **LOCAL ONLY** — not yet on GitHub. Tagged `v0.1.0`.

| Day | Scope | Status |
|---|---|---|
| 1 | Scaffold + `list_wms_layers` (WMS layer discovery) | ✅ done, verified live |
| 2 | `get_wms_map` (fetch map image) + FastMCP `server.py` wiring | ✅ done, verified live |
| 3 | `query_wfs_features` (vector features) + pytest tests + GitHub Actions CI | ✅ done (8 tests green, ruff clean) |
| 4 | Demo notebook + proper README + `docs/ARCHITECTURE.md` + CHANGELOG + tag `v0.1.0` | ✅ done (tag local) |
| 5 | GitHub publish + polish/visibility (topics, issues, links) | ⬜ not started |

> **⚠️ Unverified before release:** `examples/demo.ipynb`'s **WFS cell** uses a PDOK endpoint +
> `type_name` (`bestuurlijkegebieden:Gemeentegebied`) that was NOT run live (sandbox has no
> internet). The WMS cells use endpoints we proved live. **Run the notebook end-to-end (or just the
> WFS cell) before the Day 5 GitHub release**; fix the endpoint/type_name if needed, then re-point
> the `v0.1.0` tag (`git tag -f -a v0.1.0`) before pushing.

### What works right now
- `list_wms_layers(wms_url) -> list[LayerInfo]` — verified live against TopPlusOpen WMS
  (returned 6 layers, all `LayerInfo` fields populated correctly).
- `get_wms_map(wms_url, layer, bbox, crs, ...) -> bytes` — verified live (fetched a 412 KB
  valid PNG from TopPlusOpen). Maps the public `crs` arg to owslib's `srs`.
- `server.py` runs a FastMCP server named `mcp-ogc` exposing **both** WMS tools. Verified that
  `list_tools()` returns `['list_wms_layers', 'get_wms_map']`. The `get_wms_map` MCP tool wraps
  the core bytes in a FastMCP `Image` so clients render the map; the core function stays pure bytes.
- `query_wfs_features(wfs_url, type_name, bbox=None, max_features=100) -> dict` — returns a
  GeoJSON FeatureCollection. Spatial (bbox) filtering only; **`filter_cql` was dropped for
  v0.1.0** (see decisions). Registered as the third MCP tool.
- `server.py` exposes **all three** tools: `['list_wms_layers', 'get_wms_map', 'query_wfs_features']`.
- `mcp-ogc` console script is installed (`.venv/Scripts/mcp-ogc.exe`) → runs `mcp_ogc.server:main`.
- `examples/claude_desktop.json` provides a drop-in Claude Desktop config.
- **Test suite:** 8 hermetic tests (`tests/test_wms.py`, `tests/test_wfs.py`) — all green, no
  network. **CI:** `.github/workflows/ci.yml` runs `uv sync` + `ruff check` + `pytest` on push/PR.
- **Docs:** full `README.md` (with Mermaid architecture diagram + roadmap), `docs/ARCHITECTURE.md`,
  `CHANGELOG.md` (v0.1.0), and `examples/demo.ipynb` (3-tool walkthrough, no API key). `ruff` lints
  the notebook too — keep its cells clean.
- **Tag:** `v0.1.0` exists locally (annotated). NOT pushed. May need re-pointing if the demo WFS
  cell is fixed (see warning above).
- Project installs cleanly via `uv` on Python 3.12.

---

## Key decisions (do not silently reverse these)

| Decision | Choice | Why |
|---|---|---|
| OGC client library | `owslib` | Standard GIS library; both source briefs specify it |
| Packaging / env | `uv` (build backend: `uv_build`) | Modern, fast, single tool |
| Python version | pinned **3.12** (`.python-version`) | owslib has a documented quirk on 3.13 |
| Scope per session | one "day" at a time, clean increments | User wants slow-and-steady, no overcomplication |
| Publishing | local-only until code is seen working AND user approves | Nothing public prematurely |
| `[project.scripts]` | added in Day 2 (`mcp-ogc = "mcp_ogc.server:main"`) | Was deferred in Day 1 until `server.py` existed, to avoid a broken command |
| `get_wms_map` return type | core fn returns `bytes`; `server.py` wraps in FastMCP `Image` | Keeps the core pure/testable/reusable while clients still render the map |
| `crs` vs `srs` | public tools use `crs`; mapped to owslib's `srs` inside `get_wms_map` | owslib's `getmap()` names the param `srs` even for WMS 1.3.0 |
| WFS `filter_cql` | **dropped for v0.1.0** (bbox-only); roadmap item for v0.2 | owslib's `getfeature()` has no CQL param (only an OGC XML `filter`); CQL would need fragile vendor-specific handling |
| Test mocking lib | **`responses`**, NOT `pytest-httpx` | owslib uses the `requests` library internally; pytest-httpx only intercepts httpx and would not catch owslib's traffic |
| Git identity (repo-local) | Nikos Koulos `<nickoulos@gmail.com>` | Must be a Foursight-associated identity, set per-repo |

---

## How to run / verify

```bash
# from the repo root
uv sync                       # install deps into .venv (Python 3.12)

# verify layer discovery against a live WMS:
uv run python -c "from mcp_ogc.tools.wms import list_wms_layers; \
ls = list_wms_layers('https://sgx.geodatenzentrum.de/wms_topplus_open'); \
print(len(ls)); print(ls[0].model_dump_json(indent=2) if ls else 'NO LAYERS')"

# verify map fetch (saves test_map.png, which is gitignored):
uv run python -c "from mcp_ogc.tools.wms import get_wms_map; \
img = get_wms_map('https://sgx.geodatenzentrum.de/wms_topplus_open', 'web', \
(10.0, 50.0, 11.0, 51.0), crs='EPSG:4326', width=400, height=400); \
print('bytes:', len(img), 'PNG' if img[:8]==b'\x89PNG\r\n\x1a\n' else 'NOT PNG')"

# confirm all three tools are registered with the MCP server:
uv run python -c "import asyncio; from mcp_ogc.server import mcp; \
print([t.name for t in asyncio.run(mcp.list_tools())])"

# run the hermetic test suite + lint (no network needed — safe in any environment):
uv run pytest -q
uv run ruff check

# run the actual MCP server (waits silently on stdio for a client; Ctrl+C to stop):
uv run mcp-ogc
```

Expected: non-zero layer count; `PNG`;
`['list_wms_layers', 'get_wms_map', 'query_wfs_features']`; `8 passed`; `All checks passed!`.

### ⚠️ Network caveats (important — saves debugging time)
- **The Claude Code sandbox has NO internet** — DNS fails. Any live WMS/WFS call must be run in
  the **user's own terminal**, not via the agent's Bash tool.
- **This machine's network cannot resolve Swedish municipal hosts** (e.g. `kartor.eskilstuna.se`)
  — DNS block. For live runs use a reachable endpoint. Known-good: TopPlusOpen
  `https://sgx.geodatenzentrum.de/wms_topplus_open`. The README/demo may still *reference* a
  Swedish endpoint as the headline example, but verification runs need a reachable one.

---

## What to do next (Day 5 — PUBLISH)

**Goal:** make the repo public on GitHub under the `foursight-lab` org and publish the `v0.1.0`
release. **This is the first outward-facing step — confirm with the user before pushing anything.**

**Before pushing (do these first):**
0. **Verify the demo notebook end-to-end** in the user's terminal (the WFS cell is unverified —
   see the warning near the top). Fix the WFS endpoint/`type_name` if needed and re-point the tag:
   `git add examples/demo.ipynb && git commit --amend` (or a new commit) then
   `git tag -f -a v0.1.0 -m "..."`.

**Publish steps:**
1. `gh auth login` (currently not authenticated).
2. Create the `foursight-lab` GitHub org (manual, via GitHub UI) if it doesn't exist.
3. Create the public repo and push: `gh repo create foursight-lab/mcp-ogc --public --source=. --push`,
   then `git push --tags`.
4. Confirm the **CI badge goes green** on GitHub (CI has only been proven locally so far).
   Add the badge to the README once green.
5. Publish the `v0.1.0` **release** from the tag (`gh release create v0.1.0 ...`).
6. Add repo **description + topics**: `mcp`, `wms`, `wfs`, `ogc`, `geospatial`, `agpl-3.0`,
   `llm-tools`.
7. File 3–5 **v0.2 roadmap issues** (CQL filtering, WMTS, auth, caching) — shows planning.
8. Cross-link from foursightlab.com / LinkedIn.

After publishing: add one sentence to the procurement application
(`Org_och_kapacitet_Foursight_Lab.md`) referencing the public repo. See briefs §6/§10.

---

## Where the detailed planning docs live

These are in the **Pilot 3 docs folder** (a sibling directory, NOT inside this repo):
`../Govtech4all Pilot 3 AI och geodata/`

- `MCP_OGC_HANDOFF.md` / `MCP_OGC_BUILD_PLAN.md` — the original full 5-day briefs (source of truth
  for scope and the day-by-day plan).
- `docs/superpowers/specs/2026-05-29-mcp-ogc-day1-design.md` — Day 1 design spec.
- `docs/superpowers/plans/2026-05-29-mcp-ogc-day1.md` — Day 1 step-by-step plan.

## Explicitly OUT of scope for v0.1.0 (resist the urge)

WMTS, WPS, OAuth/SAML auth (basic HTTP auth only), caching, retries/observability, exotic CRS
conversion, Kubernetes/Helm. Ship small and on time; defer everything else to v0.2+.
