"""
Take screenshots of JiraMaster app using Playwright headless Chromium.
Starts the Flask app, captures each page, then stops the app.

Usage: python3 docs/take_screenshots.py
Must be run from the JiraMaster project root.
"""
import os
import sys
import time
import subprocess
import threading
import signal
from pathlib import Path

OUT = Path(__file__).parent / "images"
OUT.mkdir(exist_ok=True)

VENV_PYTHON = Path(__file__).parent.parent / "venv" / "bin" / "python"
APP_PY      = Path(__file__).parent.parent / "app.py"
BASE_URL    = "http://127.0.0.1:5001"   # use 5001 to avoid conflicts

# Minimal config.json for the app to work without a real Jira instance
FAKE_CONFIG = '''{
  "jira_url": "https://example.atlassian.net",
  "email": "demo@example.com",
  "api_token": "DEMO_TOKEN",
  "project_key": "DEMO",
  "ac_field_id": "",
  "proxy": "",
  "labels": []
}'''

# Sample work file for pages that need loaded epics
SAMPLE_WORK = '''{
  "epics": [
    {
      "title": "User Authentication System",
      "description": "Implement secure user authentication with SSO support",
      "acceptance_criteria": "Users can log in via email/password and SSO. Sessions expire after 8 hours.",
      "due_date": "2026-06-30",
      "priority": "High",
      "assignee": "Alice Johnson",
      "comment": "Discussed in sprint planning",
      "initiative_id": "",
      "project_key": "DEMO",
      "include": true,
      "stories": [
        {
          "title": "Login page UI",
          "description": "Design and build the login form with validation",
          "acceptance_criteria": "Form validates email format and password length. Error messages are clear.",
          "due_date": "2026-05-15",
          "priority": "High",
          "assignee": "Bob Smith",
          "comment": "",
          "include": true
        },
        {
          "title": "OAuth2 SSO integration",
          "description": "Integrate with company identity provider using OAuth2",
          "acceptance_criteria": "Users can log in via SSO. Token refresh works silently.",
          "due_date": "2026-05-30",
          "priority": "Medium",
          "assignee": "Alice Johnson",
          "comment": "",
          "include": true
        }
      ]
    },
    {
      "title": "Reporting Dashboard",
      "description": "Build a real-time metrics dashboard for team leads",
      "acceptance_criteria": "Dashboard loads in < 2 seconds. Data refreshes every 30 seconds.",
      "due_date": "2026-07-15",
      "priority": "Medium",
      "assignee": "Carol Davis",
      "comment": "",
      "initiative_id": "DEMO-100",
      "project_key": "DEMO",
      "include": true,
      "stories": [
        {
          "title": "Sprint velocity chart",
          "description": "Render a line chart showing story points completed per sprint",
          "acceptance_criteria": "Chart shows last 8 sprints. Hovering shows exact values.",
          "due_date": "2026-06-20",
          "priority": "Medium",
          "assignee": "Carol Davis",
          "comment": "",
          "include": true
        }
      ]
    }
  ]
}'''


def write_fake_config(root: Path):
    cfg = root / "config.json"
    if not cfg.exists():
        cfg.write_text(FAKE_CONFIG)
        print("  wrote fake config.json")
        return True
    return False


def write_sample_work(root: Path) -> str:
    """Write a sample .work file and return the uuid."""
    import uuid
    work_dir = root / ".work"
    work_dir.mkdir(exist_ok=True)
    uid = "aaaabbbb-cccc-dddd-eeee-000011112222"
    (work_dir / f"{uid}.json").write_text(SAMPLE_WORK)
    print(f"  wrote sample work file: {uid}")
    return uid


def start_flask(root: Path, port: int = 5001):
    """Start Flask in background on given port. Returns process."""
    # Patch app.py port temporarily via a wrapper script
    wrapper = root / "_screenshot_runner.py"
    wrapper.write_text(
        f"import sys\nsys.path.insert(0, '{root}')\n"
        f"import app as _app\n"
        f"_app.app.run(debug=False, port={port}, use_reloader=False)\n"
    )
    env = os.environ.copy()
    env["FLASK_DEBUG"] = "0"
    proc = subprocess.Popen(
        [str(VENV_PYTHON), str(wrapper)],
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # wait for app to start
    for _ in range(30):
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            print(f"  Flask started on port {port}")
            return proc
        except Exception:
            pass
    print("  WARNING: Flask may not have started cleanly")
    return proc


def take_screenshots(root: Path, work_id: str, port: int = 5001):
    from playwright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{port}"

    pages_to_shot = [
        ("01_prompt",   f"{base}/prompt/",            "Step 1 — Prompt Builder"),
        ("02_import",   f"{base}/import/",            "Step 2a — Import"),
        ("03_import_view", f"{base}/import/view",     "Step 2b — Import View"),
        ("04_edit",     f"{base}/edit/",              "Step 3 — Edit"),
        ("05_upload_preview", f"{base}/upload/preview", "Step 4 — Upload Preview"),
        ("06_settings", f"{base}/settings/",          "Settings"),
        ("07_tools",    f"{base}/tools/",             "Jira Tools"),
    ]

    # Inject the work_id cookie for pages that need it
    cookies = [{"name": "session", "value": "", "domain": "127.0.0.1", "path": "/"}]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1.5,
        )
        page = context.new_page()

        # Navigate to prompt page first to set up session with work_id
        page.goto(f"{base}/prompt/", wait_until="networkidle")

        # Inject the work_id into session via a custom route (just visit pages)
        # For pages that require session data, we'll set a cookie manually
        # by hitting the import/parse route with sample data won't work without CSRF
        # Instead: we write the work file directly and set session cookie via Flask's own session
        # Simplest approach: navigate to pages and screenshot whatever renders

        for slug, url, label in pages_to_shot:
            print(f"  screenshotting {label} ...")
            try:
                # For pages that redirect without session data, just capture what we get
                page.goto(url, wait_until="networkidle", timeout=10000)
                # Wait a bit for any JS to settle
                page.wait_for_timeout(800)
                out_path = str(OUT / f"{slug}.png")
                page.screenshot(path=out_path, full_page=False)
                print(f"    ✓ {slug}.png")
            except Exception as e:
                print(f"    ✗ {label}: {e}")

        # Now try to get session-dependent pages by going through the flow
        # Visit prompt, then manually navigate with the work_id in session
        # We need to use Flask's test client approach — instead let's navigate
        # via the app normally: upload a YAML via the import page

        # Try to screenshot import/view with sample data by injecting session
        print("  Setting up session with sample work data...")
        try:
            # Go to import page, fill in the textarea with YAML, submit
            page.goto(f"{base}/import/", wait_until="networkidle")
            # Get CSRF token
            csrf_input = page.query_selector('input[name="csrf_token"]')
            if csrf_input:
                # Fill in the YAML textarea
                ta = page.query_selector('textarea[name="copilot_output"]')
                if ta:
                    ta.fill(SAMPLE_WORK)
                    page.click('button[type="submit"]')
                    page.wait_for_url("**/import/view**", timeout=5000)
                    page.wait_for_timeout(800)
                    page.screenshot(path=str(OUT / "03_import_view.png"), full_page=False)
                    print("    ✓ 03_import_view.png (with data)")

                    # Now go to edit
                    page.goto(f"{base}/edit/", wait_until="networkidle")
                    page.wait_for_timeout(800)
                    page.screenshot(path=str(OUT / "04_edit.png"), full_page=False)
                    print("    ✓ 04_edit.png (with data)")

                    # And upload preview
                    page.goto(f"{base}/upload/preview", wait_until="networkidle")
                    page.wait_for_timeout(800)
                    page.screenshot(path=str(OUT / "05_upload_preview.png"), full_page=False)
                    print("    ✓ 05_upload_preview.png (with data)")
        except Exception as e:
            print(f"    session flow error: {e}")

        browser.close()


def main():
    root = Path(__file__).parent.parent
    port = 5001

    created_config = write_fake_config(root)
    work_id = write_sample_work(root)

    print("Starting Flask app...")
    proc = start_flask(root, port)

    try:
        print("Taking screenshots...")
        take_screenshots(root, work_id, port)
    finally:
        print("Stopping Flask app...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        # Clean up fake config if we created it
        if created_config:
            cfg = root / "config.json"
            if cfg.exists():
                cfg.unlink()
                print("  removed fake config.json")

        # Clean up wrapper script
        wrapper = root / "_screenshot_runner.py"
        if wrapper.exists():
            wrapper.unlink()

    print("\nDone! Screenshots saved to docs/images/")


if __name__ == "__main__":
    main()
