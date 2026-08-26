"""FIRE fixture: optional dep imported outside try in a bounded operation."""
import os


def capture_web_page(app_url, dest_dir):
    from playwright.sync_api import sync_playwright

    page = sync_playwright().chromium.launch().new_page()
    page.goto(app_url)
    page.screenshot(path=os.path.join(dest_dir, "page.png"))
