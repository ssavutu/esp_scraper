#!/usr/bin/env python3
"""Find part-time co-op listings on Drexel's co-op job search.

How it works:
1) Opens a real Chromium window. You log in to connect.drexel.edu yourself
   (Duo and all) and navigate to the co-op job search RESULTS list, with
   whatever filters you want applied.
2) Press ENTER in the terminal. The script works out which links on the page
   are job postings (and asks you to confirm), then follows the "Next" page
   links to collect every posting.
3) It opens each posting, saves its text, and flags part-time signals:
   "part-time" wording and stated hours under --max-hours per week.
4) Writes coop_output/jobs.csv with part-time candidates first.

Setup (once):
  pip install playwright
  python -m playwright install chromium

Usage:
  python coop_parttime.py
  python coop_parttime.py --link-pattern 'JobDetail'   # skip link auto-detect
  python coop_parttime.py --max-hours 25 --delay 1.0

Login is kept in .coop_browser_profile/, so later runs usually skip it.
Posting text is cached in coop_output/jobs/, so an interrupted run picks up
where it stopped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Page, sync_playwright

START_URL = "https://connect.drexel.edu"
PROFILE_DIR = ".coop_browser_profile"
LOGIN_MARKERS = ("microsoftonline.com", "/idp/", "login", "signin", "cas/")
# Every real Banner co-op posting ("Job View") has these. When the session is
# dropped, Banner serves its "User Login" page at the posting's own URL, so the
# URL alone can't tell us we've been logged out.
POSTING_MARKERS = ("Job View", "Employer:")
LISTED_HOURS_RE = re.compile(r"Approximate Hours Per Week:\s*(\d+(?:\.\d+)?)", re.I)

PART_TIME_RE = re.compile(r"\bpart[\s-]?time\b", re.I)
FULL_TIME_RE = re.compile(r"\bfull[\s-]?time\b", re.I)
# "20 hours per week", "15-20 hrs/week", "up to 25 hours a week", "20 hours weekly"
HOURS_RE = re.compile(
    r"(\d{1,2})(?:\s*(?:-|–|to)\s*(\d{1,2}))?\s*(?:hours?|hrs?)\.?\s*(?:per|/|a|each)?\s*(?:week|wk)\b"
    r"|(\d{1,2})(?:\s*(?:-|–|to)\s*(\d{1,2}))?\s*(?:hours?|hrs?)\.?\s*weekly",
    re.I,
)
NEXT_TEXTS = re.compile(r"^\s*(next|next page|next\s*>+|>|>>|»|›)\s*$", re.I)

COLLECT_LINKS_JS = """
() => Array.from(document.querySelectorAll('a[href]')).map(a => {
  const row = a.closest('tr, li, [role=row], .row, article') || a.parentElement;
  return {
    href: a.href,
    text: (a.innerText || '').trim(),
    rowText: row ? (row.innerText || '').trim() : '',
  };
})
"""


def link_group(href: str) -> str:
    """Regex for links to the same kind of page: same host + path, IDs in the path wildcarded."""
    parts = urlsplit(href)
    return r"\d+".join(re.escape(chunk) for chunk in re.split(r"\d+", f"{parts.netloc}{parts.path}"))


def collect_links(page: Page) -> List[Dict[str, str]]:
    links = page.evaluate(COLLECT_LINKS_JS)
    return [l for l in links if l["href"].startswith("http")]


def guess_job_pattern(links: List[Dict[str, str]]) -> Optional[str]:
    # A results page is mostly one repeated "view posting" link that differs only
    # by an ID, so the biggest such group is the best guess.
    counts = Counter(link_group(l["href"]) for l in links)
    if not counts:
        return None
    group, n = counts.most_common(1)[0]
    return group if n >= 3 else None


def confirm_pattern(page: Page, pattern: Optional[str]) -> re.Pattern:
    while True:
        links = collect_links(page)
        if pattern is None:
            pattern = guess_job_pattern(links)
        while not pattern:
            pattern = input(
                "Couldn't tell which links are job postings. Paste part of a posting's URL "
                "(right-click a job > Copy link) or a regex: "
            ).strip()
        try:
            regex = re.compile(pattern)
        except re.error:
            regex = re.compile(re.escape(pattern))
        matches = [l for l in links if regex.search(l["href"])]
        print(f"\nPattern {pattern!r} matches {len(matches)} links on this page, e.g.:")
        for l in matches[:5]:
            print(f"  {l['text'][:60]!r:64} {l['href']}")
        answer = input("Are these the job postings? [Y = yes / or type a different pattern]: ").strip()
        if answer.lower() in ("", "y", "yes"):
            return regex
        pattern = answer


def job_hrefs(page: Page, regex: re.Pattern) -> List[str]:
    try:
        return [l["href"] for l in collect_links(page) if regex.search(l["href"])]
    except Exception:  # page mid-navigation
        return []


def click_next(page: Page, regex: re.Pattern, timeout: float = 20.0) -> bool:
    for el in page.query_selector_all("a, button, input[type=submit], input[type=button]"):
        label = el.inner_text() if el.evaluate("e => e.tagName") != "INPUT" else (el.get_attribute("value") or "")
        if NEXT_TEXTS.match(label or "") and el.is_visible():
            before = job_hrefs(page, regex)
            el.click()
            # Form posts and AJAX tables don't always finish loading by the time
            # click() returns, so wait until the listed postings actually change.
            deadline = time.time() + timeout
            while time.time() < deadline:
                page.wait_for_timeout(500)
                after = job_hrefs(page, regex)
                if after and after != before:
                    break
            return True
    return False


def collect_all_postings(page: Page, regex: re.Pattern) -> List[Dict[str, str]]:
    seen: Dict[str, Dict[str, str]] = {}
    page_num = 1
    while True:
        new = 0
        for l in collect_links(page):
            if regex.search(l["href"]) and l["href"] not in seen:
                seen[l["href"]] = l
                new += 1
        print(f"Results page {page_num}: +{new} postings ({len(seen)} total)")
        if new == 0 and page_num > 1:
            break
        if not click_next(page, regex):
            answer = input(
                "No 'Next' button found. If there are more result pages, go to the next one in the "
                "browser and press ENTER; otherwise type 'done': "
            ).strip()
            if answer.lower() == "done":
                break
        page_num += 1
    return list(seen.values())


def is_posting(url: str, text: str) -> bool:
    if any(marker in url.lower() for marker in LOGIN_MARKERS):
        return False
    return all(marker in text for marker in POSTING_MARKERS)


def fetch_posting_text(page: Page, url: str, pacing: Dict[str, float]) -> str:
    while True:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        text = page.inner_text("body")
        if is_posting(page.url, text):
            return text
        # Banner drops the session when requests come too fast, so slow down
        # for the rest of the run before retrying.
        pacing["delay"] *= 2
        input(
            "\nGot a login/logout page instead of a job posting, so the session was dropped.\n"
            "In the browser: go to connect.drexel.edu, open BannerWeb, and open the co-op job\n"
            f"search until you can see a job again. Then press ENTER (slowing to {pacing['delay']:.0f}s/posting)..."
        )


def classify(text: str, max_hours: int) -> Dict[str, Any]:
    hours: List[int] = []
    for m in HOURS_RE.finditer(text):
        nums = [int(g) for g in m.groups() if g]
        hours.append(max(nums))
    hours = [h for h in hours if 1 <= h <= 80]

    part_time_hits = [snippet(text, m.start()) for m in PART_TIME_RE.finditer(text)]
    full_time = bool(FULL_TIME_RE.search(text))
    low_hours = bool(hours) and max(hours) < max_hours
    listed = LISTED_HOURS_RE.search(text)
    listed_hours = float(listed.group(1)) if listed else None

    # The posting's own "Approximate Hours Per Week" field beats keyword guessing.
    if listed_hours is not None:
        if listed_hours < max_hours:
            verdict = "yes"
        elif part_time_hits or low_hours:
            verdict = "maybe"
        else:
            verdict = "no"
    elif part_time_hits and not full_time:
        verdict = "yes"
    elif part_time_hits or low_hours:
        verdict = "maybe"
    else:
        verdict = "no"

    return {
        "part_time": verdict,
        "listed_hours_per_week": "" if listed_hours is None else f"{listed_hours:g}",
        "mentions_part_time": bool(part_time_hits),
        "mentions_full_time": full_time,
        "hours_found": ", ".join(str(h) for h in sorted(set(hours))),
        "snippets": " | ".join(part_time_hits[:3]),
    }


def snippet(text: str, pos: int, width: int = 80) -> str:
    return " ".join(text[max(0, pos - width) : pos + width].split())


def open_browser(p: Any, executable: Optional[str]) -> BrowserContext:
    return p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
        executable_path=executable,
        ignore_https_errors=True,
        viewport=None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Flag part-time Drexel co-op postings")
    parser.add_argument("--link-pattern", help="Regex matching posting URLs (skips auto-detect)")
    parser.add_argument("--max-hours", type=int, default=30, help="Hours/week below this count as part-time")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Seconds between postings (Banner logs you out if this is too low)")
    parser.add_argument("--out-dir", default="coop_output", help="Where to write jobs.csv and cached text")
    parser.add_argument("--chromium", help="Path to a Chromium/Chrome binary (default: Playwright's)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    cache_dir = out_dir / "jobs"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = open_browser(p, args.chromium)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(START_URL, wait_until="domcontentloaded")

        input(
            "\nIn the browser: log in, open the co-op job search, apply your filters, and get to the "
            "first page of RESULTS.\nThen press ENTER here..."
        )
        (out_dir / "results_page_1.html").write_text(page.content(), encoding="utf-8")

        regex = confirm_pattern(page, args.link_pattern)
        postings = collect_all_postings(page, regex)
        if not postings:
            print("No postings collected.", file=sys.stderr)
            return 1

        detail_page = context.new_page()
        pacing = {"delay": args.delay}
        rows: List[Dict[str, Any]] = []
        for i, posting in enumerate(postings, 1):
            url = posting["href"]
            cache = cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}.txt"
            text = cache.read_text(encoding="utf-8") if cache.exists() else ""
            # Re-fetch cached login pages saved by earlier runs.
            if not is_posting(url, text):
                try:
                    text = fetch_posting_text(detail_page, url, pacing)
                except Exception as exc:  # one bad posting shouldn't kill a long run
                    print(f"  [{i}/{len(postings)}] failed: {url} ({exc})", file=sys.stderr)
                    continue
                cache.write_text(f"{url}\n\n{text}", encoding="utf-8")
                time.sleep(pacing["delay"] * random.uniform(1.0, 1.5))

            # The results-table row often has hours/type columns too, so check both.
            info = classify(posting["rowText"] + "\n" + text, args.max_hours)
            rows.append({"title": posting["text"] or posting["rowText"][:80], "url": url, **info,
                         "text_file": str(cache)})
            print(f"  [{i}/{len(postings)}] {info['part_time']:5} {rows[-1]['title'][:70]}")

        context.close()

    if not rows:
        print("Every posting failed to load.", file=sys.stderr)
        return 1
    order = {"yes": 0, "maybe": 1, "no": 2}
    rows.sort(key=lambda r: order[r["part_time"]])
    csv_path = out_dir / "jobs.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    tally = Counter(r["part_time"] for r in rows)
    print(f"\nWrote {csv_path}: {tally['yes']} part-time, {tally['maybe']} maybe, {tally['no']} no")
    print(f"Tip: grep -il 'part-time' {cache_dir}/* to double-check by hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
