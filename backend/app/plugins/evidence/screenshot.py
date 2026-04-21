"""Evidence collection: Playwright headless browser screenshots."""
from __future__ import annotations

import asyncio
import io
import uuid
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)


async def capture_screenshot(
    url: str,
    engagement_id: str | uuid.UUID,
    finding_id: str | uuid.UUID | None = None,
    full_page: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    timeout_ms: int = 30000,
) -> str | None:
    """Capture a screenshot of a URL and store it in MinIO.

    Args:
        url: The URL to screenshot.
        engagement_id: UUID of the engagement (used for MinIO path).
        finding_id: Optional UUID of the finding this screenshot is for.
        full_page: Whether to capture the full scrollable page.
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
        timeout_ms: Navigation timeout in milliseconds.

    Returns:
        The MinIO object key where the screenshot was stored, or None on failure.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("evidence.screenshot_unavailable", reason="playwright not installed")
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe_url = url.replace("://", "_").replace("/", "_").replace(":", "_")[:80]
    if finding_id:
        filename = f"{timestamp}_{safe_url}_finding_{finding_id}.png"
    else:
        filename = f"{timestamp}_{safe_url}.png"

    object_key = f"artifacts/{engagement_id}/screenshots/{filename}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            except Exception:
                # Fallback: wait for load instead of networkidle
                try:
                    await page.goto(url, timeout=timeout_ms, wait_until="load")
                except Exception:
                    await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

            screenshot_bytes = await page.screenshot(full_page=full_page, type="png")
            await browser.close()

        # Store to MinIO
        await _store_screenshot(object_key, screenshot_bytes)
        logger.info("evidence.screenshot_captured", url=url, path=object_key, size=len(screenshot_bytes))
        return object_key

    except Exception as e:
        logger.error("evidence.screenshot_error", url=url, error=str(e))
        return None


async def capture_screenshots_batch(
    urls: list[str],
    engagement_id: str | uuid.UUID,
    max_concurrent: int = 3,
) -> dict[str, str | None]:
    """Capture screenshots for multiple URLs concurrently.

    Returns:
        Dict mapping URL -> MinIO object key (or None if failed).
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def capture_one(url: str) -> tuple[str, str | None]:
        async with semaphore:
            key = await capture_screenshot(url, engagement_id)
            return url, key

    tasks = [capture_one(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, str | None] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error("evidence.batch_screenshot_error", error=str(result))
        elif isinstance(result, tuple):
            url, key = result
            output[url] = key

    return output


async def _store_screenshot(object_key: str, data: bytes) -> None:
    """Store screenshot bytes to MinIO."""
    try:
        from app.config import get_settings
        from minio import Minio

        settings = get_settings()
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET_ARTIFACTS
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        client.put_object(
            bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type="image/png",
        )
    except Exception as e:
        logger.warning("evidence.screenshot_store_error", path=object_key, error=str(e))
        raise
