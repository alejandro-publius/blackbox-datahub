"""End-to-end browser drill of the judge-facing demo flow.

Drives the real UI (frontend :3000 + backend :8400 + DataHub :9002) through:
intake → investigate → root cause → repair & verify → resolution → reset,
capturing screenshots into docs/screenshots/ and failing on console errors.

Run: uv run python scripts/demo_drill.py  (services must be up; warehouse in incident mode)
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

APP = "http://localhost:3000"
DATAHUB = "http://localhost:9002"
INVESTIGATION_TIMEOUT_MS = 8 * 60 * 1000

console_errors: list[str] = []


def shoot(page, name: str) -> None:
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  📸 {name}")


RAW_ORDERS_URN = "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)"


def datahub_login(browser):
    """Log into the local DataHub UI and dismiss the first-run product tour."""
    dh = browser.new_page(viewport={"width": 1680, "height": 1000}, device_scale_factor=2)
    dh.goto(f"{DATAHUB}/login", wait_until="networkidle", timeout=30000)
    dh.fill('input[name="username"], input[type="text"]', "datahub")
    dh.fill('input[type="password"]', "datahub")
    dh.keyboard.press("Enter")
    dh.wait_for_timeout(4000)
    return dh


def dismiss_tour(dh) -> None:
    for sel in ['button[aria-label="Close"]', ".ant-modal-close", 'button:has-text("Skip")']:
        try:
            dh.locator(sel).first.click(timeout=2000)
            break
        except Exception:
            continue
    dh.wait_for_timeout(600)


def click_button(page, patterns: list[str], timeout: int = 15000) -> None:
    for pat in patterns:
        loc = page.get_by_role("button", name=re.compile(pat, re.I)).first
        try:
            loc.wait_for(state="visible", timeout=timeout // len(patterns))
            loc.click()
            return
        except PWTimeout:
            continue
    raise AssertionError(f"no clickable button matched {patterns}")


def main() -> int:
    resume = "--resume" in sys.argv  # continue an incident already at ROOT_CAUSE_CONFIRMED
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1680, "height": 1000}, device_scale_factor=2)
        page.on(
            "console",
            lambda m: console_errors.append(m.text) if m.type == "error" else None,
        )

        if resume:
            print("RESUME — loading page with in-flight incident")
            page.goto(APP, wait_until="networkidle", timeout=60000)
            page.get_by_text(re.compile(r"ROOT CAUSE CONFIRMED", re.I)).first.wait_for(
                state="visible", timeout=60000
            )
        else:
            print("ACT 1 — intake (anomalous KPI)")
            page.goto(APP, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            body = page.inner_text("body")
            assert "PREVIEW" not in body, "preview watermark visible on live page!"
            if not re.search(r"(×|x)\s*EXPECTED|CRITICAL|ANOMAL", body, re.I):
                failures.append("intake: no anomaly indicator found on load")
            shoot(page, "01-intake.png")

            print("ACT 2 — start investigation")
            click_button(page, [r"investigate"])
            page.wait_for_timeout(800)
            # dialog with prefilled report; submit it
            click_button(page, [r"start", r"investigate", r"report", r"submit"])

            print("ACT 3 — live investigation → root cause")
            page.wait_for_timeout(15000)
            shoot(page, "02-investigation.png")
            try:
                page.get_by_text(re.compile(r"ROOT CAUSE CONFIRMED", re.I)).first.wait_for(
                    state="visible", timeout=INVESTIGATION_TIMEOUT_MS
                )
            except PWTimeout:
                shoot(page, "failure-no-rootcause.png")
                failures.append("investigation never reached ROOT CAUSE CONFIRMED (8 min)")
                print("FAILURES:", failures)
                browser.close()
                return 1
            page.wait_for_timeout(1000)
            shoot(page, "03-rootcause.png")

            # The DataHub incident is raised ACTIVE the moment the cause is proven —
            # capture it here, because after the repair it flips to RESOLVED and the
            # Incidents tab (which lists ACTIVE only) would look empty.
            try:
                dh = datahub_login(browser)
                dh.goto(
                    f"{DATAHUB}/dataset/{RAW_ORDERS_URN}/Incidents",
                    wait_until="networkidle", timeout=30000,
                )
                dh.wait_for_timeout(2500)
                dismiss_tour(dh)
                dh.wait_for_timeout(1200)
                if not re.search(r"BlackBox", dh.inner_text("body"), re.I):
                    failures.append("DataHub Incidents tab shows no BlackBox incident while ACTIVE")
                dh.screenshot(path=str(SHOTS / "05-datahub-incident.png"))
                print("  📸 05-datahub-incident.png (ACTIVE)")
                dh.close()
            except Exception as e:
                failures.append(f"datahub ACTIVE incident capture failed: {e}")

        print("ACT 4 — repair & verify")
        # Two Repair buttons exist: the top-bar one is BEHIND the overlay backdrop
        # (pointer events blocked → click times out); the overlay card's own CTA is
        # last in DOM and clickable.
        page.get_by_role("button", name=re.compile(r"repair\s*&?\s*verify", re.I)).last.click(
            timeout=15000
        )
        try:
            page.get_by_text(re.compile(r"INCIDENT RESOLVED", re.I)).first.wait_for(
                state="visible", timeout=INVESTIGATION_TIMEOUT_MS
            )
        except PWTimeout:
            shoot(page, "failure-no-resolution.png")
            failures.append("repair never reached INCIDENT RESOLVED (8 min)")
            print("FAILURES:", failures)
            browser.close()
            return 1
        page.wait_for_timeout(1200)
        body = page.inner_text("body")
        for expected in [r"32\s*/\s*32", r"blackbox/fix-", r"(writeback|resolved.+datahub|urn:li:incident)"]:
            if not re.search(expected, body, re.I):
                failures.append(f"resolution screen missing {expected!r}")
        shoot(page, "04-resolved.png")

        print("ACT 5 — DataHub carries the durable remediation record")
        try:
            dh = datahub_login(browser)
            dh.goto(
                f"{DATAHUB}/dataset/{RAW_ORDERS_URN}/Documentation",
                wait_until="networkidle", timeout=30000,
            )
            dh.wait_for_timeout(2500)
            dismiss_tour(dh)
            try:  # expand the truncated docs so the incident-history note is visible
                dh.get_by_text(re.compile(r"show more", re.I)).first.click(timeout=3000)
                dh.wait_for_timeout(800)
            except Exception:
                pass
            body = dh.inner_text("body")
            for expected in [r"Incident history", r"blackbox|BlackBox"]:
                if not re.search(expected, body, re.I):
                    failures.append(f"DataHub docs missing remediation note ({expected})")
            dh.screenshot(path=str(SHOTS / "05b-datahub-remediation.png"))
            print("  📸 05b-datahub-remediation.png (RESOLVED + note)")
            dh.close()
        except Exception as e:
            failures.append(f"datahub remediation capture failed: {e}")

        print("ACT 6 — reset returns to broken state")
        click_button(page, [r"reset"])
        page.wait_for_timeout(2000)
        try:
            page.get_by_text(re.compile(r"(×|x)\s*EXPECTED|CRITICAL|ANOMAL", re.I)).first.wait_for(
                state="visible", timeout=120000
            )
        except PWTimeout:
            failures.append("after reset: anomalous intake state not restored")
        page.wait_for_timeout(1500)
        shoot(page, "06-reset-intake.png")

        browser.close()

    serious = [e for e in console_errors if "favicon" not in e.lower()]
    if serious:
        failures.append(f"{len(serious)} console errors, first: {serious[0][:200]}")
    if failures:
        print("\n❌ DRILL FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("\n✅ demo drill passed end-to-end; screenshots in docs/screenshots/")
    return 0


if __name__ == "__main__":
    t0 = time.time()
    rc = main()
    print(f"({time.time() - t0:.0f}s)")
    sys.exit(rc)
