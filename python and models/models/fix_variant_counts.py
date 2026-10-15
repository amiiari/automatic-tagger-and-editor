#!/usr/bin/env python3
"""
One-time repair of spelling-variant counts in master_taglist.csv.

The refresh flow only ADDS batch increments for tags discovered after the
original seed scrape, so late-added tags carry tiny stale counts (red_eyes
sat at 437 while the site has ~838k). That breaks the batch tagger's
canonicalization, which picks the highest-count spelling among variants
(red_eye/red_eyes, big_/large_, 1girl/1girls...).

This script finds every group of general tags that are spelling variants of
each other, asks the Rule34 API for their TRUE counts, and rewrites just
those rows. A timestamped .bak of the CSV is written first.

Usage:  python fix_variant_counts.py        (run from the models folder)
"""

import configparser
import csv
import datetime
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "master_taglist.csv")
CONFIG = os.path.join(os.path.dirname(HERE), "config.ini")
API = "https://api.rule34.xxx/index.php?page=dapi&s=tag&q=index"


def variants(tag):
    out = {tag, tag + "s"}
    if tag.endswith("s"):
        out.add(tag[:-1])
    for t in list(out):
        if "large" in t:
            out.add(t.replace("large", "big"))
        if "big" in t:
            out.add(t.replace("big", "large"))
    return out


def api_count(name, creds):
    url = f"{API}&name={urllib.parse.quote(name)}&limit=1{creds}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                xml = r.read().decode("utf-8", "replace")
            m = re.search(r'count="(\d+)"[^>]*name="' + re.escape(name) + '"', xml) \
                or re.search(r'name="' + re.escape(name) + '"[^>]*count="(\d+)"', xml)
            return int(m.group(1)) if m else None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def main():
    cp = configparser.ConfigParser()
    cp.read(CONFIG, encoding="utf-8")
    creds = cp.get("api", "api_key", fallback="")
    if not creds:
        sys.exit("No API key in config.ini - run customize.bat and add it first.")

    rows = []
    gen = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.reader(f):
            rows.append(row)
            if len(row) >= 3 and row[1].strip() == "0":
                gen[row[0].strip().lower()] = row

    seen, todo = set(), []
    for t in gen:
        if t in seen:
            continue
        group = sorted(v for v in variants(t) if v in gen)
        if len(group) > 1:
            todo.extend(group)
            seen.update(group)
    print(f"{len(todo)} tags in spelling-variant groups - fetching true counts "
          f"(~{len(todo) * 0.35 / 60:.0f} min at 3/s)...")

    changed = failed = 0
    for i, name in enumerate(todo, 1):
        true_count = api_count(name, creds)
        if true_count is None:
            failed += 1
        else:
            row = gen[name]
            old = row[2].strip()
            if old != str(true_count):
                row[2] = str(true_count)
                changed += 1
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}  (changed {changed}, failed {failed})")
        time.sleep(0.35)

    stamp = datetime.date.today().isoformat()
    backup = CSV_PATH + f".bak-{stamp}"
    if not os.path.exists(backup):
        shutil.copy2(CSV_PATH, backup)
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"done: {changed} counts corrected, {failed} lookups failed "
          f"(kept old counts). Backup: {os.path.basename(backup)}")


if __name__ == "__main__":
    main()
