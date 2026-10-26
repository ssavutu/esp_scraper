# Finding part-time co-op listings

`coop_parttime.py` goes through every Drexel co-op job posting you can see and
flags the ones that look part-time. You log in yourself in a normal browser
window; the script never sees your password.

## 1) Install (once)

Needs Python 3.9+.

```bash
git clone https://github.com/ssavutu/esp_scraper.git
cd esp_scraper
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install playwright
python -m playwright install chromium
```

## 2) Run

```bash
python coop_parttime.py
```

1. A Chromium window opens on connect.drexel.edu. Log in (Duo included).
2. Open the co-op job search, set any filters you want, and search. If there's a
   "results per page" option, set it as high as it goes.
3. When you're on the **first page of results**, go back to the terminal and
   press **ENTER**.
4. It prints the links it thinks are job postings. If they look right, press
   ENTER. If not, right-click a job title > Copy link, and paste part of that
   URL that's the same for every job (e.g. `JobDetail`).
5. It clicks "Next" through the results on its own. If it can't find the Next
   button, it asks you to go to the next page yourself and press ENTER; type
   `done` after the last page.
6. It then opens every posting, one by one, about one every 3-4 seconds (Banner
   logs you out if it goes faster). ~270 postings takes 15-20 minutes. Leave
   the window alone until it finishes.
7. If Banner logs you out anyway, it pauses and tells you. In the browser, go
   to connect.drexel.edu > BannerWeb > co-op job search until you can see a
   job again, then press ENTER. It retries and slows itself down further.

## 3) The output

Everything lands in `coop_output/`:

- **`coop_output/jobs.csv`**: open it in Excel or Google Sheets. One row per
  posting, sorted so likely part-time jobs come first:
  - `part_time`: `yes`, `maybe` or `no`. It goes by the posting's
    "Approximate Hours Per Week" field (`yes` if under 30); postings without
    that field fall back to looking for "part-time" wording.
  - `listed_hours_per_week`: that field's value
  - `hours_found`: any "N hours per week" numbers in the description text
  - `snippets`: the text around each "part-time" mention, so you can check it
  - `url`: link to the posting (opens while you're logged in)
- **`coop_output/jobs/`**: the full text of each posting, one file each.
- **`coop_output/results_page_1.html`**: a saved copy of the first results
  page, useful if something goes wrong.

Check the `maybe` rows by hand: the script only looks for words like
"part-time" and hour counts, so it can't read between the lines.

## Options

```bash
python coop_parttime.py --max-hours 25            # stricter hours cutoff (default 30)
python coop_parttime.py --link-pattern JobDetail  # skip the link-guessing step
python coop_parttime.py --delay 5                 # slower if you keep getting logged out (default 3)
```

Running it again is fast: postings already saved in `coop_output/jobs/` are
not re-downloaded, and the login is remembered in `.coop_browser_profile/`.
Delete `coop_output/` to start completely fresh.

## If it doesn't work

If it says it can't tell which links are postings, or the CSV is empty, send
`coop_output/results_page_1.html` to whoever gave you this script. Don't send
`.coop_browser_profile/`, because that folder holds your login.
