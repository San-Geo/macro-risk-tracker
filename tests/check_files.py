"""Parse every data/config file the tracker reads. A malformed upload (a missing comma
in a JSON file, a bad indent in YAML, a broken CSV row) fails here within a minute of
the push - instead of silently breaking the next daily run.

    python tests/check_files.py
"""
import csv
import glob
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bad = []
n = 0
for pattern in ("data/*.json", "dashboard/*.json", "config/*.yaml", "config/*.yml",
                ".github/workflows/*.yml", "dashboard/briefs/editions/*.json"):
    for p in sorted(glob.glob(os.path.join(ROOT, pattern))):
        n += 1
        try:
            with open(p) as f:
                (json.load if p.endswith(".json") else yaml.safe_load)(f)
        except Exception as e:
            bad.append(f"{os.path.relpath(p, ROOT)}: {e}")
for p in sorted(glob.glob(os.path.join(ROOT, "data", "archive", "*", "*.jsonl"))):
    n += 1
    with open(p) as f:
        for i, line in enumerate(f, start=1):
            if line.strip():
                try:
                    json.loads(line)
                except Exception as e:
                    bad.append(f"{os.path.relpath(p, ROOT)} line {i}: {e}")
                    break
for p in sorted(glob.glob(os.path.join(ROOT, "data", "*.csv"))) + [
        os.path.join(ROOT, f) for f in ("grades.csv", "manual_input.csv")]:
    if not os.path.exists(p):
        continue
    n += 1
    try:
        with open(p, newline="") as f:
            rows = list(csv.reader(f))
        if rows:
            width = len(rows[0])
            for i, r in enumerate(rows[1:], start=2):
                if not r or r[0].lstrip().startswith("#"):
                    continue          # blank lines and comment lines are fine
                # more fields than the header = an unquoted comma (e.g. in a note);
                # fewer is allowed (older rows written before a column was added)
                if len(r) > width:
                    raise ValueError(f"line {i} has {len(r)} fields, header has {width} "
                                     f"- put a note containing commas in double quotes")
    except Exception as e:
        bad.append(f"{os.path.relpath(p, ROOT)}: {e}")

if bad:
    for b in bad:
        print(f"::error title=Malformed file::{b}")
    sys.exit(1)
print(f"All {n} data/config files parse cleanly.")
