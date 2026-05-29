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

**As of 2026-05-29: Day 1 complete.** Repo is **LOCAL ONLY** — not yet on GitHub.

| Day | Scope | Status |
|---|---|---|
| 1 | Scaffold + `list_wms_layers` (WMS layer discovery) | ✅ done, verified live |
| 2 | `get_wms_map` (fetch map image) + FastMCP `server.py` wiring | ⬜ not started |
| 3 | `query_wfs_features` (vector features) + pytest tests + GitHub Actions CI | ⬜ not started |
| 4 | Demo notebook + proper README + `docs/ARCHITECTURE.md` + tag `v0.1.0` | ⬜ not started |
| 5 | GitHub publish + polish/visibility (topics, issues, links) | ⬜ not started |

### What works right now
- `list_wms_layers(wms_url) -> list[LayerInfo]` — verified live against TopPlusOpen WMS
  (returned 6 layers, all `LayerInfo` fields populated correctly).
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
| `[project.scripts]` | **intentionally omitted in Day 1** | Console script targets `server.py` (Day 2); declaring it now = broken `mcp-ogc` command |
| Tests | none yet — pytest is Day 3 work | Day 1/2 verify manually against live endpoints |
| Git identity (repo-local) | Nikos Koulos `<nickoulos@gmail.com>` | Must be a Foursight-associated identity, set per-repo |

---

## How to run / verify

```bash
# from the repo root
uv sync                       # install deps into .venv (Python 3.12)

# verify the one working tool against a live WMS:
uv run python -c "from mcp_ogc.tools.wms import list_wms_layers; \
ls = list_wms_layers('https://sgx.geodatenzentrum.de/wms_topplus_open'); \
print(len(ls)); print(ls[0].model_dump_json(indent=2) if ls else 'NO LAYERS')"
```

Expected: a non-zero layer count and a populated `LayerInfo` JSON object.

### ⚠️ Network caveats (important — saves debugging time)
- **The Claude Code sandbox has NO internet** — DNS fails. Any live WMS/WFS call must be run in
  the **user's own terminal**, not via the agent's Bash tool.
- **This machine's network cannot resolve Swedish municipal hosts** (e.g. `kartor.eskilstuna.se`)
  — DNS block. For live runs use a reachable endpoint. Known-good: TopPlusOpen
  `https://sgx.geodatenzentrum.de/wms_topplus_open`. The README/demo may still *reference* a
  Swedish endpoint as the headline example, but verification runs need a reachable one.

---

## What to do next (Day 2)

**Goal:** add `get_wms_map` and stand up the actual MCP server so an AI client can attach.

1. Implement `get_wms_map(wms_url, layer, bbox, crs, width, height, image_format, time) -> bytes`
   in `src/mcp_ogc/tools/wms.py`, using `owslib`'s `wms.getmap(...)`.
   - **GOTCHA:** owslib's `getmap()` takes `srs=` (not `crs=`). The public tool signature uses
     `crs` (per the briefs), so map `crs` → owslib's `srs` inside the function.
   - Return `img.read()` (raw image bytes).
2. Create `src/mcp_ogc/server.py` with FastMCP and register the tools:
   ```python
   from mcp.server.fastmcp import FastMCP
   from mcp_ogc.tools.wms import list_wms_layers, get_wms_map
   mcp = FastMCP("mcp-ogc")
   mcp.tool()(list_wms_layers)
   mcp.tool()(get_wms_map)
   def main(): mcp.run()
   if __name__ == "__main__": main()
   ```
3. **Now** add the console script to `pyproject.toml` (it was deliberately deferred):
   ```toml
   [project.scripts]
   mcp-ogc = "mcp_ogc.server:main"
   ```
4. Add `examples/claude_desktop.json` sample config.
5. Verify the server starts and a client can call both tools.

After Day 2, see the day-by-day plan for Days 3–5.

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
