"""Browser audit of native controls. Start theme_preview.py on port 8502 first."""

import json
from pathlib import Path

from scripts.audit_ui import CONTRAST_AUDIT, wait_for_app
from src.settings import settings


def run():
    from playwright.sync_api import sync_playwright

    output = Path(settings.excel_artifact_dir) / "ui_audit"
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            page.goto("http://127.0.0.1:8502")
            wait_for_app(page, "Theme validation preview")
            result = {"width": width, "initial": page.evaluate(CONTRAST_AUDIT)}
            result["controls"] = page.locator(
                'input:not([tabindex="-1"])'
            ).evaluate_all("""es=>es.filter(e=>!e.closest('[aria-hidden=true]')).map(e=>({
              label:e.getAttribute('aria-label'),color:getComputedStyle(e).color,
              placeholder:getComputedStyle(e,'::placeholder').color,
              placeholderOpacity:getComputedStyle(e,'::placeholder').opacity
            }))""")
            page.get_by_role("combobox", name="Source type").click()
            page.get_by_role("option", name="Independent FRED", exact=True).wait_for()
            result["dropdown"] = page.evaluate(CONTRAST_AUDIT)
            page.screenshot(path=str(output / f"widgets-dropdown-{width}.png"), full_page=True)
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Choose date", exact=True).click()
            page.get_by_role("dialog").wait_for()
            result["calendar"] = page.evaluate(CONTRAST_AUDIT)
            page.screenshot(path=str(output / f"widgets-date-{width}.png"), full_page=True)
            page.keyboard.press("Escape")
            details = page.locator("summary").filter(has_text="Source details")
            details.click()
            details.scroll_into_view_if_needed()
            result["expanded"] = page.evaluate(CONTRAST_AUDIT)
            page.screenshot(path=str(output / f"widgets-alerts-{width}.png"), full_page=True)
            assert not page.locator('[data-testid="stException"]').count()
            results.append(result)
            print(
                width,
                {
                    k: len(result[k]["failures"])
                    for k in ("initial", "dropdown", "calendar", "expanded")
                },
                flush=True,
            )
            page.close()
        browser.close()
    (output / "widget-report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return (
        1
        if any(
            r[k]["failures"]
            for r in results
            for k in ("initial", "dropdown", "calendar", "expanded")
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(run())
