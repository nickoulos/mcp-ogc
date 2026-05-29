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

**As of 2026-05-29: Days 1–2 complete.** Repo is **LOCAL ONLY** — not yet on GitHub.

| Day | Scope | Status |
|---|---|---|
| 1 | Scaffold + `list_wms_layers` (WMS layer discovery) | ✅ done, verified live |
| 2 | `get_wms_map` (fetch map image) + FastMCP `server.py` wiring | ✅ done, verified live |
| 3 | `query_wfs_features` (vector features) + pytest tests + GitHub Actions CI | ⬜ not started |
| 4 | Demo notebook + proper README + `docs/ARCHITECTURE.md` + tag `v0.1.0` | ⬜ not started |
| 5 | GitHub publish + polish/visibility (topics, issues, links) | ⬜ not started |

### What works right now
- `list_wms_layers(wms_url) -> list[LayerInfo]` — verified live against TopPlusOpen WMS
  (returned 6 layers, all `LayerInfo` fields populated correctly).
- `get_wms_map(wms_url, layer, bbox, crs, ...) -> bytes` — verified live (fetched a 412 KB
  valid PNG from TopPlusOpen). Maps the public `crs` arg to owslib's `srs`.
- `server.py` runs a FastMCP server named `mcp-ogc` exposing **both** WMS tools. Verified that
  `list_tools()` returns `['list_wms_layers', 'get_wms_map']`. The `get_wms_map` MCP tool wraps
  the core bytes in a FastMCP `Image` so clients render the map; the core function stays pure bytes.
- `mcp-ogc` console script is installed (`.venv/Scripts/mcp-ogc.exe`) → runs `mcp_ogc.server:main`.
- `examples/claude_desktop.json` provides a drop-in Claude Desktop config.
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
| Tests | none yet — pytest is Day 3 work | Day 1/2 verify manually against live endpoints |
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

# confirm both tools are registered with the MCP server:
uv run python -c "import asyncio; from mcp_ogc.server import mcp; \
print([t.name for t in asyncio.run(mcp.list_tools())])"

# run the actual MCP server (waits silently on stdio for a client; Ctrl+C to stop):
uv run mcp-ogc
```

Expected: non-zero layer count; `PNG`; `['list_wms_layers', 'get_wms_map']`.

### ⚠️ Network caveats (important — saves debugging time)
- **The Claude Code sandbox has NO internet** — DNS fails. Any live WMS/WFS call must be run in
  the **user's own terminal**, not via the agent's Bash tool.
- **This machine's network cannot resolve Swedish municipal hosts** (e.g. `kartor.eskilstuna.se`)
  — DNS block. For live runs use a reachable endpoint. Known-good: TopPlusOpen
  `https://sgx.geodatenzentrum.de/wms_topplus_open`. The README/demo may still *reference* a
  Swedish endpoint as the headline example, but verification runs need a reachable one.

---

## What to do next (Day 3)

**Goal:** add the third tool (`query_wfs_features`), the first automated tests, and CI.

1. Implement `query_wfs_features(wfs_url, type_name, bbox=None, filter_cql=None, max_features=100) -> dict`
   in a new `src/mcp_ogc/tools/wfs.py`, using `owslib.wfs.WebFeatureService(wfs_url, version="2.0.0")`.
   - Call `wfs.getfeature(typename=type_name, bbox=bbox, ...)` requesting `outputFormat="application/json"`.
   - Parse the response as JSON and return a GeoJSON FeatureCollection dict.
   - **Likely GOTCHAs (verify against current owslib):** WFS 2.0.0 param naming
     (`typename` vs `typenames`), how `maxfeatures`/`count` is spelled, and how CQL filters are passed.
     Check owslib docs before assuming the brief's signature maps 1:1.
2. Register it in `server.py` (add an `@mcp.tool()` for `query_wfs_features`, same pattern as the
   WMS tools). It returns a plain dict, so no `Image` wrapper needed.
3. Add `tests/` with pytest + `pytest-httpx` (add them as dev deps via `uv add --dev`):
   - Mock the HTTP responses (GetCapabilities, GetMap, GetFeature) — do NOT hit live endpoints in CI.
   - `tests/test_wms.py` (4–6 tests), `tests/test_wfs.py` (3–4 tests).
4. Add `ruff` as a dev dep; ensure `ruff check` passes.
5. Add `.github/workflows/ci.yml`: on push, `uv sync`, `uv run pytest`, `uv run ruff check`.
6. **Network note:** CI must use mocks (GitHub runners can reach the internet, but live WMS calls
   are flaky and slow — keep tests hermetic). The live endpoint checks stay manual / local.

After Day 3: Day 4 = demo notebook + proper README + `docs/ARCHITECTURE.md` + tag `v0.1.0`;
Day 5 = GitHub publish + visibility. See the briefs for detail.

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
