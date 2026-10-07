#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Send an analysis bundle to local deepseek-r1 and print its reasoning + verdict.

The model is deepseek-r1 on the tailnet (VM3). It is offline/local — no cloud.
R1 emits its chain of thought in ``message.thinking`` and the answer in
``message.content``; this prints both. It thinks a lot, so the token budget is
generous and the request can take minutes.

Usage:
    uv run python scripts/r1_analyze.py /tmp/bundle2h.json
    uv run python scripts/r1_analyze.py /tmp/bundle2h.json --model deepseek-r1:latest \
        --url http://100.110.82.97:11434 --num-predict 6000
"""

from __future__ import annotations

import argparse
import json
import urllib.request

SYSTEM = (
    "You are a trading-forensics analyst for a Polymarket US sports trader. "
    "You are given a JSON bundle of his fills in a time window, the market price "
    "path (market_temperature) for each market he traded, and the game state. "
    "Ground every claim in the bundle's timestamps and prices. Do not invent data. "
    "If the bundle does not support a claim, say so. Be specific and quantitative."
)


def run(url: str, model: str, bundle: dict, num_predict: int, temperature: float, num_ctx: int) -> dict:
    questions = "\n".join(f"{i+1}. {q}" for i, q in enumerate(bundle.get("analysis_questions", [])))
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": (
                "Here is the trading bundle as JSON:\n\n"
                + json.dumps(bundle)
                + "\n\nAnswer these questions, each with its evidence:\n" + questions
            )},
        ],
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": temperature, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        f"{url}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run local deepseek-r1 over an analysis bundle.")
    ap.add_argument("bundle", help="path to the analysis bundle JSON")
    ap.add_argument("--url", default="http://100.110.82.97:11434", help="Ollama base URL (tailnet)")
    ap.add_argument("--model", default="deepseek-r1:latest")
    ap.add_argument("--num-predict", type=int, default=6000)
    ap.add_argument("--num-ctx", type=int, default=16384, help="context window (R1 default 4096 rejects the bundle)")
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--out", metavar="FILE", help="write reasoning+answer to a file")
    args = ap.parse_args()

    with open(args.bundle) as fh:
        bundle = json.load(fh)

    print(f"sending {args.bundle} to {args.model} at {args.url} (num_predict={args.num_predict}, num_ctx={args.num_ctx}) ...")
    resp = run(args.url, args.model, bundle, args.num_predict, args.temperature, args.num_ctx)
    msg = resp.get("message") or {}
    thinking = msg.get("thinking") or ""
    content = msg.get("content") or ""

    out = []
    if thinking:
        out.append("=== REASONING ===\n" + thinking.strip())
    out.append("=== VERDICT ===\n" + (content.strip() or "(empty — raise --num-predict; R1 was still thinking)"))
    text = "\n\n".join(out)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    print(text)
    print(f"\n[eval_count={resp.get('eval_count')} done_reason={resp.get('done_reason')}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
