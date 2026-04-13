from playwright.sync_api import sync_playwright
import requests
import json
import os
from requests.cookies import create_cookie

DUPROD_URL = "https://connect.drexel.edu/duprod/hwczkfsea.P_StudentESaPArchiveList"
COOKIE_FILE = "cookies.json"

def build_session_from_cookies(cookies):
    session = requests.Session()

    for c in cookies:
        cookie = create_cookie(
            name=c["name"],
            value=c["value"],
            domain=c.get("domain"),
            path=c.get("path", "/"),
        )
        session.cookies.set_cookie(cookie)

    return session

def get_session_via_login():
    with sync_playwright() as manager:
        browser = manager.chromium.launch(
            executable_path="/usr/bin/chromium-browser",
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        page.goto("https://connect.drexel.edu", wait_until="domcontentloaded")

        input("Log in fully in the browser, then press ENTER...")

        page.goto(DUPROD_URL, wait_until="domcontentloaded")

        print("Inside duprod, extracting cookies...")

        cookies = context.cookies()
        browser.close()

    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, indent=2)

    return build_session_from_cookies(cookies)

def load_session():
    with open(COOKIE_FILE, "r") as f:
        cookies = json.load(f)

    return build_session_from_cookies(cookies)

def is_session_valid(session):
    try:
        res = session.get(DUPROD_URL, timeout=10)

        # Must still be on duprod AND contain expected content
        if "/duprod/" in res.url and ("ES&P" in res.text or "Archive" in res.text):
            return True

        return False

    except:
        return False

def get_session():
    if os.path.exists(COOKIE_FILE):
        print("Loading existing session...")

        session = load_session()

        if is_session_valid(session):
            print("Session is valid")
            return session
        else:
            print("Session expired")

    print("Starting new login...")
    return get_session_via_login()

if __name__ == "__main__":
    session = get_session()

    res = session.get(DUPROD_URL)

    print("Final URL:", res.url)
    print("Status:", res.status_code)
    print(res.text[:500])