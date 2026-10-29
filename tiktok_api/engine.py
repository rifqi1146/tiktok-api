import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger("tiktok.engine")

WARM_URL = "https://www.tiktok.com/explore"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


def _chrome_path() -> Optional[str]:
    """Prefer system Chrome; fall back to Playwright's bundled Chromium."""
    for p in ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"):
        if os.path.exists(p):
            return p
    return None




class TikTokBrowserEngine:
    """
    Chromium engine that keeps warmed TikTok pages ready for in-page API calls.

    Every API request must be issued from inside a page: the webmssdk bundle
    patches window.fetch and appends the X-Bogus / X-Gnarly / X-Dynosaur query
    signatures plus msToken. Plain HTTP clients get an empty 200 from the edge.

    A small pool of warmed pages avoids the "execution context destroyed" race
    that a single shared page hits when one request navigates while another
    evaluates.
    """

    def __init__(
        self,
        pool_size: int = 3,
        headless: Optional[bool] = None,
        executable_path: Optional[str] = None,
    ):
        self.pool_size = int(os.environ.get("POOL_SIZE", pool_size))
        # HEADLESS defaults to false (headed): Akamai WAF rejects pure headless on
        # cold SSR pages, so run_api.sh supplies a virtual X display via Xvfb.
        if headless is None:
            self.headless = os.environ.get("HEADLESS", "0") in ("1", "true", "True")
        else:
            self.headless = headless
        self.executable_path = executable_path or os.environ.get("CHROME_PATH") or _chrome_path()
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None          # warm reference page (SSR navigations)
        self._pool: "asyncio.Queue[Page]" = asyncio.Queue()
        self._start_lock = asyncio.Lock()
        self._ready = False

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._ready:
            return
        async with self._start_lock:
            if self._ready:
                return
            logger.info("starting chromium (pool=%d)", self.pool_size)
            self._pw = await async_playwright().start()
            launch_kwargs = {
                "headless": self.headless,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--no-first-run",
                ],
            }
            if self.executable_path:
                launch_kwargs["executable_path"] = self.executable_path
            self._browser = await self._pw.chromium.launch(**launch_kwargs)
            self._context = await self._browser.new_context(
                locale="en-US",
                viewport={"width": 1440, "height": 900},
                user_agent=UA,
            )
            await self._context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )

            self._page = await self._context.new_page()
            await self._warm(self._page)
            self._ready = True

            for _ in range(self.pool_size):
                page = await self._context.new_page()
                await self._warm(page)
                self._pool.put_nowait(page)
            logger.info("engine ready: 1 ssr page + %d api pages", self.pool_size)

    async def _warm(self, page: Page) -> None:
        """Loads a TikTok page so cookies, ttwid, msToken and webmssdk exist."""
        await page.goto(WARM_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)

    async def stop(self) -> None:
        logger.info("stopping chromium")
        try:
            if self._browser:
                await self._browser.close()
        except Exception as exc:                                   # noqa: BLE001
            logger.warning("browser close failed: %s", exc)
        try:
            if self._pw:
                await self._pw.stop()
        except Exception as exc:                                   # noqa: BLE001
            logger.warning("playwright stop failed: %s", exc)
        self._ready = False

    async def _ensure(self) -> None:
        if not self._ready:
            await self.start()

    # ------------------------------------------------------------- api (in-page)
    async def evaluate(self, script: str, arg: Any = None) -> Any:
        """Runs JS on a pooled warmed page; the page is returned to the pool after."""
        await self._ensure()
        page = await self._pool.get()
        try:
            if page.is_closed():
                page = await self._context.new_page()
                await self._warm(page)
            return await page.evaluate(script, arg) if arg is not None else await page.evaluate(script)
        finally:
            if not page.is_closed():
                self._pool.put_nowait(page)

    # ------------------------------------------------------------------ ssr page
    async def fetch_scope(self, url: str) -> Optional[Dict[str, Any]]:
        """Opens a fresh page in the authenticated context and returns __DEFAULT_SCOPE__.

        A reused tab that already navigated to another TikTok path can surface
        net::ERR_HTTP_RESPONSE_CODE_FAILURE even when the target document is
        served normally, so each SSR read gets its own short-lived page.
        """
        await self._ensure()
        page = await self._context.new_page()
        try:
            # A cold page asking for a deep TikTok URL directly gets Akamai's
            # "HTTP ERROR 403 / Access denied". Warming the tab first (same tab,
            # same origin, cookies and referer chain established) and then
            # navigating from inside the document serves the page normally.
            await page.goto(WARM_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1200)
            await page.evaluate("(u) => { window.location.href = u; }", url)
            await page.wait_for_timeout(3500)
            raw = await page.evaluate(
                "() => document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent || ''"
            )
            if not raw:
                snip = await page.evaluate(
                    "() => (document.body && document.body.innerText || '').slice(0, 160)"
                )
                logger.info("fetch_scope empty for %s (url_now=%s): %r", url, page.url, snip)
                return None
            try:
                return json.loads(raw).get("__DEFAULT_SCOPE__", {})
            except json.JSONDecodeError:
                logger.warning("invalid rehydration json for %s", url)
                return None
        except Exception as exc:                                   # noqa: BLE001
            logger.warning("fetch_scope failed for %s: %s", url, exc)
            return None
        finally:
            await page.close()
    async def get_cookies(self) -> Dict[str, str]:
        """Returns session cookies for authenticated CDN proxying."""
        await self._ensure()
        if not self._context:
            return {}
        return {c["name"]: c["value"] for c in await self._context.cookies()}

engine = TikTokBrowserEngine()
