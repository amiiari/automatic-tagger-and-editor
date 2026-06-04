#!/usr/bin/env python3
"""
Refresh master_taglist.csv by fetching recent posts from the Rule34 API.

Updates existing tag counts by adding post occurrences from the fetched batch.
New tags are appended at the bottom of the CSV.
Existing tags are never deleted.

Usage:
    refresh_tags.bat
"""

import csv
import os
import sys
import time
import configparser
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from collections import defaultdict, OrderedDict
from pathlib import Path

# Enable ANSI colors on Windows
import ctypes
if sys.platform == "win32":
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ANSI color codes
GREEN  = "\033[92m"
BLUE   = "\033[94m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

TYPE_NAMES = {
    0: "General",
    1: "Character",
    3: "Metadata",
    4: "Copyright",
    5: "Artist",
}

API_BASE = "https://api.rule34.xxx/index.php"
CSV_PATH = Path(__file__).parent / "master_taglist.csv"
HEADERS  = {"User-Agent": "r34-tag-updater/1.0"}

CONFIG_DIR  = Path(__file__).resolve().parent
PROJECT_DIR = CONFIG_DIR.parent
PROJECT_ROOT = PROJECT_DIR.parent
CONFIG_FILE = PROJECT_DIR / "config.ini"

MIN_POSTS = 50


def read_config():
    """Read config.ini, return (max_posts, api_user_id, api_key, target_tag)."""
    cp = configparser.ConfigParser()
    cp.read(CONFIG_FILE, encoding="utf-8")
    max_posts = cp.getint("batch", "max_posts", fallback=2000)
    api_user_id = cp.get("api", "user_id", fallback="").strip()
    api_key = cp.get("api", "api_key", fallback="").strip()
    target_tag = cp.get("target_tag", "tag", fallback="").strip()
    return max_posts, api_user_id, api_key, target_tag


def read_existing_csv():
    """Load existing CSV. Returns (tag_types dict, tag_counts dict, ordered list of tag names)."""
    tag_types = {}
    tag_counts = {}
    tag_order = []  # preserve original order

    if CSV_PATH.exists():
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    name = row[0].strip()
                    try:
                        ttype = int(row[1])
                        count = int(row[2])
                    except ValueError:
                        continue
                    tag_types[name] = ttype
                    tag_counts[name] = count
                    tag_order.append(name)
    return tag_types, tag_counts, tag_order


def build_auth_suffix(api_key, api_user_id):
    """Build auth suffix, handling both raw key and full query string formats."""
    if api_key and "api_key=" in api_key and "user_id=" in api_key:
        return api_key  # already a full query string
    return f"api_key={api_key}&user_id={api_user_id}"


def fetch_posts(pid=0, limit=100, tag="", auth_suffix=""):
    url = (
        f"{API_BASE}?page=dapi&s=post&q=index"
        f"&limit={limit}&pid={pid}"
    )
    if auth_suffix:
        url += auth_suffix if auth_suffix.startswith("&") else f"&{auth_suffix}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise
    except Exception as e:
        raise ConnectionError(f"Request failed: {e}")


def fetch_tag_posts(tag, pid=0, limit=100, auth_suffix=""):
    """Fetch paginated posts for a specific tag using pid."""
    url = (
        f"{API_BASE}?page=dapi&s=post&q=index"
        f"&limit={limit}"
        f"&tags={urllib.parse.quote(tag)}"
    )
    if pid:
        url += f"&pid={pid}"
    if auth_suffix:
        url += auth_suffix if auth_suffix.startswith("&") else f"&{auth_suffix}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise
    except Exception as e:
        raise ConnectionError(f"Request failed: {e}")


def parse_posts(xml):
    """Parse XML response into list of (post_id, tag_lists)."""
    posts = []
    for post in ET.fromstring(xml).findall(".//post"):
        post_id = post.get("id", "")
        tags = [t.strip() for t in post.get("tags", "").split() if t.strip()]
        if tags:
            posts.append((post_id, tags))
    return posts


def refresh_tags():
    print(f"{BOLD}Loading CSV...{RESET}")
    existing_types, existing_counts, tag_order = read_existing_csv()
    print(f"Loaded {len(existing_counts)} existing tags from CSV")

    # Track counts from this run
    run_counts = defaultdict(int)  # tag -> count in fetched posts
    pid = 0
    fetched = 0
    requests = 0
    start = time.time()
    last_request_time = start
    prev_fetched = 0
    elapsed = 0

    # Read config from config.ini
    MAX_POSTS, api_user_id, api_key, target_tag = read_config()

    final_api_user_id = os.environ.get("API_USER_ID", api_user_id)
    final_api_key     = os.environ.get("API_KEY", api_key)

    if not final_api_key:
        print(f"\n{BOLD}{YELLOW}⚠ No API key configured.{RESET}")
        print(f"Set API_USER_ID and API_KEY in 1. r34 tag.bat or via the Settings GUI.")
        return

    auth_suffix = build_auth_suffix(final_api_key, final_api_user_id)

    # Progress bar + live tag feed
    bar_w = 40
    print(f"\nScanning {MAX_POSTS} recent posts...")
    live_tags = []  # rolling window of newly seen tags
    first_iter = True

    # When a target_tag is set, the API only returns the most recent 100 posts
    # regardless of pid. So we only need one request.
    if target_tag:
        MAX_POSTS = 100

    while fetched < MAX_POSTS:
        batch = 100
        remaining = min(batch, MAX_POSTS - fetched)

        try:
            if target_tag:
                xml = fetch_tag_posts(target_tag, pid=pid, limit=remaining, auth_suffix=auth_suffix)
            else:
                xml = fetch_posts(pid=pid, limit=remaining, auth_suffix=auth_suffix)
        except Exception as e:
            print(f"\n{YELLOW}Request error: {e}{RESET}")
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"\n{YELLOW}Rate limited (429). Stopping.{RESET}")
                break
            elif e.code == 403:
                print(f"\n{YELLOW}403 Forbidden — API key may be revoked.{RESET}")
                break
            elif e.code >= 500:
                print(f"\n{YELLOW}Server error {e.code}. Retrying in 60s...{RESET}")
                time.sleep(60)
                continue
            else:
                print(f"\n{YELLOW}HTTP {e.code}: {e.reason}.{RESET}")
                break
        except ConnectionError as e:
            print(f"\n{YELLOW}Connection error: {e}. Retrying in 30s...{RESET}")
            time.sleep(30)
            continue
        except Exception as e:
            print(f"\n{YELLOW}Error: {e}.{RESET}")
            break

        posts = parse_posts(xml)
        if not posts:
            # Check if this is an error response
            root = ET.fromstring(xml)
            if root.tag == 'error':
                err_msg = root.text or root.get('message', 'Unknown error')
                print(f"\n{YELLOW}API error: {err_msg}{RESET}")
                break
            # API returned no more results — stop
            if target_tag:
                print(f"\n{YELLOW}No posts found for tag '{target_tag}'. API may be restricted.{RESET}")
            break
        # If we got fewer posts than requested, API has no more — stop
        if len(posts) < remaining:
            break

        # Accumulate tag counts from this batch
        last_pid = posts[-1][0]
        for _, tags in posts:
            for t in tags:
                if run_counts[t] == 0:  # first time seeing this tag
                    live_tags.append(t)
                run_counts[t] += 1

        fetched += len(posts)
        requests += 1
        pid = int(last_pid) if last_pid else pid + remaining

        # Hard limit: ensure exactly 1.5s per request cycle
        cycle_elapsed = time.time() - last_request_time
        sleep_time = 1.5 - cycle_elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
        last_request_time = time.time()

        # Terminate if API is restricted (no progress for 5s after first fetch)
        if requests > 0 and time.time() - start > 5 and fetched == prev_fetched:
            print(f"\n{YELLOW}API restricted — no progress for 5s. Stopping.{RESET}")
            break
        prev_fetched = fetched

        # Progress
        elapsed = time.time() - start
        prog = fetched / MAX_POSTS
        filled = int(bar_w * prog)
        bar = "+" * filled + "-" * (bar_w - filled)
        rate = requests / elapsed if elapsed > 0 else 0
        remaining_est = (elapsed / prog) - elapsed if prog > 0 else 0

        # Live tag feed — show last few newly seen tags
        feed = ""
        if live_tags:
            shown = live_tags[-12:]
            feed = "  " + "  ".join(shown)

        # Build the full output as one block
        line1 = f"  [{bar}] {prog:.0%}  |  {fetched:>5,d} posts  |  {len(run_counts):>6,d} unique tags  |  {rate:.1f} req/s  |  ~{remaining_est:.0f}s left"
        line2 = feed if feed else ""

        if first_iter:
            first_iter = False
        else:
            # Go up 2 lines back to the progress bar, then to start
            print("\x1b[2A\r", end="", flush=True)

        # Print both lines, clearing old content with space padding
        print(line1, end="", flush=True)
        print("\x1b[K\n", end="", flush=True)  # clear remaining of line 1, go to line 2
        print("\r" + line2 + " " * max(0, 80 - len(line2)), end="", flush=True)  # clear and write line 2

    print()  # newline after progress

    # Merge: existing tags keep their counts, new tags appended
    new_tags = [t for t in run_counts if t not in existing_counts]
    updated_tags = [t for t in run_counts if t in existing_counts and run_counts[t] > 0]

    # Write CSV — existing tags unchanged, new tags appended
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for name in tag_order:
            if existing_counts[name] >= MIN_POSTS:
                writer.writerow([name, existing_types.get(name, 0), existing_counts[name]])

        # Append new tags sorted by count desc
        for name in sorted(new_tags, key=lambda x: run_counts[x], reverse=True):
            cnt = run_counts[name]
            if cnt >= MIN_POSTS:
                writer.writerow([name, 0, cnt])

    # Final summary
    final_count = sum(1 for name in tag_order if existing_counts[name] >= MIN_POSTS) + len([t for t in new_tags if run_counts[t] >= MIN_POSTS])

    print(f"\n{BOLD}Done!{RESET}  Fetched {fetched} posts in {elapsed:.0f}s")
    if target_tag:
        print(f"  Target: {target_tag}")
    print(f"  {CYAN}{len(new_tags):,d}{RESET} new tags found  (existing tags kept as-is)")
    print(f"  CSV: {final_count:,d} tags (>= {MIN_POSTS} posts)")

    # Type breakdown
    print(f"\n  {BOLD}By type:{RESET}")
    for ttype in [0, 1, 3, 4, 5]:
        before = sum(1 for t in tag_order if existing_types.get(t, 0) == ttype and existing_counts[t] >= MIN_POSTS)
        after = sum(1 for t in tag_order if existing_types.get(t, 0) == ttype and existing_counts[t] >= MIN_POSTS)
        after += sum(1 for t in new_tags if existing_types.get(t, 0) == ttype and run_counts[t] >= MIN_POSTS)
        diff = after - before
        color = {0: GREEN, 1: BLUE, 3: YELLOW, 4: CYAN, 5: MAGENTA}.get(ttype, RESET)
        print(f"    {color}{TYPE_NAMES[ttype]:<12}{RESET}  {before:>7,d}  ->  {after:>7,d}  ({diff:+d})")

    print(f"\n  Elapsed: {elapsed:.0f}s")


if __name__ == "__main__":
    refresh_tags()
