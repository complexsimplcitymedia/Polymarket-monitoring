Here is the compiled handoff document based on the state of the project, the current infrastructure, and the immediate next steps required to get the Polymarket Intelligence dashboard operational.

---

# Polymarket Intelligence: Project State & Handoff Summary

## 1. System Architecture & Fleet Status

Your environment is split cleanly between a local staging area and the UpCloud tailnet.

* **Local Staging (WSL/USB):** USB drive mounted at `/mnt/usb`. Holds the source code (with corrupted `.git` history), the new `weather-mcp` clone, and the newly generated `deploy-07.sh` script. Nothing persistent runs here.
* **Node 06 (100.110.82.53 | 16GB RAM | `tag:dev`):** **LLM Host.**
* **Status:** Online. Port 11434 (Ollama) is verified open and reachable via Tailscale.
* **Models:** `qwen2.5:3b`, `qwen2.5:7b`, and `deepseek-r1:latest` are pulled and pinned to memory (`keep_alive: -1`) to eliminate cold-start latency.


* **Node 07 (100.110.82.54 | 8GB RAM | `tag:dev`):** **API & UI Host.**
* **Status:** Provisioned but unreachable. All ports are closed, and Docker is not yet installed.



## 2. Completed Milestones

* **Agent Migration (`agents/debate.py`):** Refactored to use a LangChain fallback sequence. Claude is primary; Gemini is the fallback if Anthropic is rate-limited or lacks a key. A `_llm_text()` normalizer was added to handle adaptive thinking blocks.
* **Deployment Script (`deploy-07.sh`):** Prepared on the USB. Once run on Node 07, it will install Docker, pull the repos, set the `.env` to point `OLLAMA_BASE_URL` to Node 06, and bring up the API (8000) and UI (5173).
* **Trading Guardrails:** `AUTO_TRADE_ENABLED=False` and `AUTO_TRADE_DRY_RUN=True` are set. No Polymarket private key is configured, making order placement structurally impossible while allowing predictions to run freely.

## 3. Immediate Technical Blockers

1. **Tailscale ACL (SSH Block):** This is the root cause of the deployment stall. Nodes 06 and 07 are tagged `tag:dev`. Your current Tailscale ACL only permits SSH to `autogroup:self` (user-owned devices).
2. **GitHub Repo is Empty:** The `deploy-07.sh` script clones `complexsimplcitymedia/Polymarket-monitoring-`, but that remote repo is currently empty. The local intact source code must be pushed there first.
3. **DeepSeek-R1 Token Bug:** DeepSeek is currently failing silently on predictions. It spends its token budget on `<think>` reasoning blocks and returns an empty string before reaching a verdict. `num_predict` must be increased, and the text parser in `parlay.py` needs to strip `<think>` blocks before evaluating the output.

## 4. Pending Features to Build

* **Sequential Parlay Cross-Reference:** Implement the gated checking logic in `parlay.py`. Qwen2.5 will execute the first pass; if a parlay meets the EV threshold, DeepSeek-R1 will run sequentially to confirm the verdict.

---

### ⚠️ Critical Security Notice

The following active API tokens were exposed in plain text during the terminal session. Once the deployment is stable, **you must rotate these immediately**:

* UpCloud API Token: ucat_01M2MDTQ6YC5R8W4G4P48JTJXK

* GitHub Personal Access Token: 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

* Tailscale Auth Key: tskey-auth-kviL51ipAd11CNTRL-PwvzEyAq9MgVjeucpurdLgEH5TS26fK1

* Tailscale API Token: tskey-api-k9Mcmw3uUe11CNTRL-S6dUghLqi5BA5TB7qjHw5Bki15Cv9eYL
