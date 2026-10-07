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
    target, keys = Path(sys.argv[1]), sys.argv[2:]
    set_keys(target, {k: os.environ[k] for k in keys})
