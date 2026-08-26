"""SILENT fixture: guarded import inside try, or non-optional import."""


def capture_web_page(app_url, dest_dir):
    try:
        from playwright.sync_api import sync_playwright
        page = sync_playwright().chromium.launch().new_page()
        page.goto(app_url)
    except Exception:
        pass


def helper():
    import json
    return json.dumps({})
