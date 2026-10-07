#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Run the trigger-discovery analysis over an analysis bundle, one model pass at a time.

Sequential by design: pass 1 on the primary host, then pass 2 on the secondary.
The full bundle goes to EACH model — no chunking — with a >=8192 token context so
nothing is truncated. Each pass writes its own output file so results can be compared.

Usage:
    # single pass
    python scripts/r1_triggers.py /tmp/bundle2h.json --url http://100.110.82.97:11434 \
        --model deepseek-r1:latest --num-ctx 16384 --num-predict 8000 --out /tmp/triggers_vm3.txt

    # sequential two-pass (primary then secondary)
    python scripts/r1_triggers.py /tmp/bundle2h.json --secondary-url http://100.110.82.53:11434 \
        --secondary-model llama3.2:latest --out /tmp/triggers_vm3.txt --out2 /tmp/triggers_vm2.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT = HERE / "trigger_prompt.txt"


def run_pass(url: str, model: str, system: str, user: str, num_ctx: int, num_predict: int,
             temperature: float) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": temperature},
    }
    req = urllib.request.Request(
        f"{url}/api/chat", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:800]
        sys.exit(f"[{url} {model}] HTTP {e.code}: {body}")


def render(resp: dict) -> str:
    m = resp.get("message") or {}
    thinking = (m.get("thinking") or "").strip()
    content = (m.get("content") or "").strip()
    parts = []
    if thinking:
        parts.append("=== REASONING ===\n" + thinking)
    parts.append("=== REPORT ===\n" + (content or "(empty — raise --num-predict)"))
    parts.append(f"[model={resp.get('model')} eval_count={resp.get('eval_count')} "
                 f"done_reason={resp.get('done_reason')}]")
    return "\n\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sequential trigger-discovery analysis over a bundle.")
    ap.add_argument("bundle")
    ap.add_argument("--url", default="http://100.110.82.97:11434")
    ap.add_argument("--model", default="deepseek-r1:latest")
    ap.add_argument("--secondary-url", help="second host for the sequential second pass")
    ap.add_argument("--secondary-model", default="deepseek-r1:latest")
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--num-predict", type=int, default=8000)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--out", help="file for pass 1 output")
    ap.add_argument("--out2", help="file for pass 2 output")
    args = ap.parse_args()

    system = PROMPT.read_text()
    bundle = json.loads(Path(args.bundle).read_text())
    user = "Here is the bundle:\n\n" + json.dumps(bundle)

    print(f"PASS 1 -> {args.model} @ {args.url}  (ctx={args.num_ctx}, predict={args.num_predict})", flush=True)
    r1 = run_pass(args.url, args.model, system, user, args.num_ctx, args.num_predict, args.temperature)
    t1 = render(r1)
    if args.out:
        Path(args.out).write_text(t1)
        print(f"  wrote {args.out}", flush=True)
    print(t1[-1500:], flush=True)

    if args.secondary_url:
        print(f"\nPASS 2 -> {args.secondary_model} @ {args.secondary_url}", flush=True)
        r2 = run_pass(args.secondary_url, args.secondary_model, system, user,
                      args.num_ctx, args.num_predict, args.temperature)
        t2 = render(r2)
        if args.out2:
            Path(args.out2).write_text(t2)
            print(f"  wrote {args.out2}", flush=True)
        print(t2[-1500:], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
