"""Tests for Phase 4 evidence collection (screenshot utility)."""
from __future__ import annotations

import asyncio
import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _stub_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_stubs() -> None:
    stubs = ["structlog", "minio", "app", "app.config"]
    for s in stubs:
        if s not in sys.modules:
            _stub_module(s)

    sl = sys.modules["structlog"]
    if not hasattr(sl, "get_logger"):
        class _Logger:
            def debug(self, *a, **kw): pass
            def info(self, *a, **kw): pass
            def warning(self, *a, **kw): pass
            def error(self, *a, **kw): pass
        sl.get_logger = lambda *a, **kw: _Logger()


_ensure_stubs()

from app.plugins.evidence.screenshot import capture_screenshot, capture_screenshots_batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_ENGAGEMENT_ID = str(uuid.uuid4())
TEST_FINDING_ID = str(uuid.uuid4())
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # fake PNG bytes


def _make_playwright_mock():
    """Build a minimal mock of the Playwright async API."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock(return_value=FAKE_PNG)

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = AsyncMock()
    chromium.launch = AsyncMock(return_value=browser)

    playwright = AsyncMock()
    playwright.chromium = chromium
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)

    return playwright, page, browser


# ---------------------------------------------------------------------------
# capture_screenshot
# ---------------------------------------------------------------------------

class TestCaptureScreenshot:
    def test_returns_none_when_playwright_missing(self):
        """If playwright is not installed, should return None gracefully."""
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            result = asyncio.get_event_loop().run_until_complete(
                capture_screenshot("https://example.com", TEST_ENGAGEMENT_ID)
            )
        assert result is None

    def test_returns_object_key_on_success(self):
        playwright_mock, page_mock, browser_mock = _make_playwright_mock()

        async def run():
            with patch("app.plugins.evidence.screenshot._store_screenshot", new=AsyncMock()):
                with patch(
                    "app.plugins.evidence.screenshot.async_playwright",
                    return_value=playwright_mock,
                ):
                    return await capture_screenshot(
                        "https://example.com",
                        TEST_ENGAGEMENT_ID,
                    )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is not None
        assert TEST_ENGAGEMENT_ID in result
        assert result.endswith(".png")
        assert "screenshots" in result

    def test_object_key_includes_finding_id(self):
        playwright_mock, _, _ = _make_playwright_mock()

        async def run():
            with patch("app.plugins.evidence.screenshot._store_screenshot", new=AsyncMock()):
                with patch(
                    "app.plugins.evidence.screenshot.async_playwright",
                    return_value=playwright_mock,
                ):
                    return await capture_screenshot(
                        "https://example.com",
                        TEST_ENGAGEMENT_ID,
                        finding_id=TEST_FINDING_ID,
                    )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is not None
        assert "finding" in result

    def test_returns_none_on_error(self):
        playwright_mock, page_mock, _ = _make_playwright_mock()
        page_mock.goto = AsyncMock(side_effect=Exception("Navigation timeout"))
        page_mock.screenshot = AsyncMock(side_effect=Exception("Page failed"))

        async def run():
            with patch("app.plugins.evidence.screenshot._store_screenshot", new=AsyncMock()):
                with patch(
                    "app.plugins.evidence.screenshot.async_playwright",
                    return_value=playwright_mock,
                ):
                    return await capture_screenshot(
                        "https://broken.example.com",
                        TEST_ENGAGEMENT_ID,
                    )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is None

    def test_object_key_structure(self):
        playwright_mock, _, _ = _make_playwright_mock()

        async def run():
            with patch("app.plugins.evidence.screenshot._store_screenshot", new=AsyncMock()):
                with patch(
                    "app.plugins.evidence.screenshot.async_playwright",
                    return_value=playwright_mock,
                ):
                    return await capture_screenshot(
                        "https://example.com/path",
                        TEST_ENGAGEMENT_ID,
                    )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is not None
        # Path structure: artifacts/{engagement_id}/screenshots/{filename}.png
        parts = result.split("/")
        assert parts[0] == "artifacts"
        assert parts[1] == TEST_ENGAGEMENT_ID
        assert parts[2] == "screenshots"
        assert parts[3].endswith(".png")


# ---------------------------------------------------------------------------
# capture_screenshots_batch
# ---------------------------------------------------------------------------

class TestCaptureScreenshotsBatch:
    def test_batch_returns_dict_of_results(self):
        urls = ["https://a.com", "https://b.com", "https://c.com"]
        call_count = 0

        async def fake_capture(url, engagement_id, **_kwargs):
            nonlocal call_count
            call_count += 1
            return f"artifacts/{engagement_id}/screenshots/{url.replace('https://', '')}.png"

        async def run():
            with patch(
                "app.plugins.evidence.screenshot.capture_screenshot",
                side_effect=fake_capture,
            ):
                return await capture_screenshots_batch(urls, TEST_ENGAGEMENT_ID)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert len(result) == 3
        for url in urls:
            assert url in result
            assert result[url] is not None

    def test_batch_handles_partial_failures(self):
        urls = ["https://good.com", "https://bad.com"]

        async def fake_capture(url, engagement_id, **_kwargs):
            if "bad" in url:
                return None
            return f"artifacts/{engagement_id}/screenshots/good.png"

        async def run():
            with patch(
                "app.plugins.evidence.screenshot.capture_screenshot",
                side_effect=fake_capture,
            ):
                return await capture_screenshots_batch(urls, TEST_ENGAGEMENT_ID)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["https://good.com"] is not None
        assert result["https://bad.com"] is None

    def test_batch_empty_urls(self):
        async def run():
            return await capture_screenshots_batch([], TEST_ENGAGEMENT_ID)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result == {}
