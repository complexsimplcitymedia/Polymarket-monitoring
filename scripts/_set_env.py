#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Set KEY=value lines in an env file, replacing existing keys and appending new ones.

Usage: _set_env.py <env file> KEY [KEY ...]   (values are read from the environment)
Values are double-quoted so passwords with spaces, '#' or '$' survive.
"""
import os
import sys
from pathlib import Path


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_keys(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    remaining = dict(updates)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in remaining:
            out.append(f"{key}={quote(remaining.pop(key))}")
        else:
            out.append(line)
    out += [f"{k}={quote(v)}" for k, v in remaining.items()]
    path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(f"Usage: {sys.argv[0]} <env_file> KEY [KEY ...]", file=sys.stderr)
        print("Values are read from existing environment variables.", file=sys.stderr)
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 1)

    target = Path(sys.argv[1])
    keys = sys.argv[2:]
    if not keys:
        print(f"No keys specified to update in {target}", file=sys.stderr)
        sys.exit(0)

    updates = {k: os.environ[k] for k in keys if k in os.environ}
    missing = [k for k in keys if k not in os.environ]
    if missing:
        print(f"Warning: Keys not present in environment: {', '.join(missing)}", file=sys.stderr)

    set_keys(target, updates)

