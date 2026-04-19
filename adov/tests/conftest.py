"""
Shared fixtures for all TripMind Playwright tests.

Usage:
    pytest tests/ -v            # headless (fast, for CI)
    pytest tests/ -v --headed   # watch a real browser window
"""
import os
import pytest

BASE_URL = "http://localhost:5173"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


# ── CLI option ────────────────────────────────────────────────────────────────

def pytest_addoption(parser):
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run Chromium in headed (visible) mode",
    )


# ── Session-scoped: one browser process for the whole test run ────────────────

@pytest.fixture(scope="session")
def _playwright():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(_playwright, request):
    headed = request.config.getoption("--headed")
    b = _playwright.chromium.launch(headless=not headed)
    yield b
    b.close()


# ── Function-scoped: each test gets a fresh page ──────────────────────────────

@pytest.fixture
def page(browser):
    """Fresh browser tab, pre-navigated to the app and fully loaded."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(BASE_URL)
    pg.wait_for_load_state("domcontentloaded")
    # Wait for React shell to render
    pg.wait_for_selector("textarea", timeout=10000)
    # Wait for getMessages() fetch to complete so currentUserId is set.
    # SSE keeps the connection alive so networkidle never fires — instead we
    # wait for either a message bubble or the empty-state placeholder to appear.
    # Wait for getMessages() to complete — currentUserId is set when data-user-id appears
    pg.wait_for_function(
        "() => document.querySelector('[data-user-id]') !== null",
        timeout=15000,
    )
    yield pg
    context.close()


# ── Screenshot helper available as a fixture ─────────────────────────────────

@pytest.fixture
def screenshot(page):
    """Returns a callable: screenshot('filename') saves to tests/screenshots/."""
    def _snap(name: str) -> str:
        path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        page.screenshot(path=path, full_page=True)
        print(f"\n  📸 saved: tests/screenshots/{name}.png")
        return path
    return _snap
