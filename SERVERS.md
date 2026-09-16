# Server Architecture

## Node 06 — Pipeline Runner
**Tailscale IP:** `100.110.82.53`  
**RAM:** 16GB  
**Role:** CrewAI sports intelligence pipeline, Ollama LLM/embedding inference

### What runs here
- `/opt/crewai/polymarket-pipeline/pipeline/sports_crew_pipeline.py` — main pipeline entrypoint
- `/opt/crewai/venv` — Python virtualenv with CrewAI 1.15.21 and all pipeline deps
- **Ollama** (`localhost:11434`) with:
  - `qwen3-embedding:4b` — vector embeddings for pgai
  - `qwen3-embedding:0.6b` — lightweight embedding fallback
  - `deepseek-r1:latest` — primary reasoning model for CrewAI agents
  - `qwen2.5:3b` / `qwen2.5:7b` — supplementary LLMs

### Pipeline flow
1. Fetches live standings + recency data from ESPN API (NFL/NBA) and MLB Stats API
2. Computes momentum scores and regime tags for all teams (MLB 30, NFL 32, NBA 30)
3. Upserts all 92 team rows into Server 7's PostgreSQL deterministically
4. Flags teams with recency/season discrepancies for CrewAI analysis
5. Recency Analyst agent generates trading narratives for flagged teams
6. Vector Librarian agent embeds narratives via pgai → pgvector on Server 7

### Pipeline repo
Private: `github.com/complexsimplcitymedia/polymarket-pipeline`  
Deployed via read-only deploy key (ed25519) — no PAT on server.

---

## Server 7 — Database + API
**Tailscale IP:** `100.110.82.54`  
**RAM:** 7.7GB  
**Role:** PostgreSQL + pgai/pgvector, FastAPI backend, Caddy reverse proxy

### What runs here
- **PostgreSQL 17** with pgai + pgvector extensions
- **FastAPI** backend (uvicorn, port 8000) — sports scanner routes + all market endpoints
- **Caddy** — reverse proxy, TLS termination
- **Docker** — containerized services

### Database schema
- `sports_teams` — `PRIMARY KEY (sport, team_id)`, all 3 sports in one table
- `sports_recency_splits` — `UNIQUE (sport, team_id, date_recorded)`, `stats JSONB`
- Embeddings stored via `ai.ollama_embed()` pointing to Node 06's Ollama (`100.110.82.53:11434`)

### API routes (sports)
| Route | Description |
|---|---|
| `GET /api/scanners/mlb/board` | All 30 MLB teams ranked by momentum |
| `GET /api/scanners/mlb/team/{id}` | MLB team deep-dive |
| `GET /api/scanners/nfl/board` | All 32 NFL teams ranked by momentum |
| `GET /api/scanners/nfl/team/{id}` | NFL team deep-dive |
| `GET /api/scanners/nba/board` | All 30 NBA teams ranked by momentum |
| `GET /api/scanners/nba/team/{id}` | NBA team deep-dive |

---

## WSL Ubuntu — SSH Bridge
**Tailscale IP:** `100.110.82.182`  
**Role:** Only reliable SSH bridge from Windows host to Tailscale mesh

Native Windows Tailscale has auth issues (`BRICE-HP\brice` vs `BRICE-HP\d_ada`).  
All remote commands route through: `wsl -d Ubuntu -- ssh root@<tailscale-ip>`

