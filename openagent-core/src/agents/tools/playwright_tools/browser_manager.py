from playwright.async_api import async_playwright
import asyncio
from datetime import datetime, timedelta

# Global browser manager to avoid serialization issues
class BrowserManager:
    """Singleton browser manager that cannot be pickled - stored globally"""
    _instance = None
    _browser = None
    _playwright = None
    _pages = {}
    _last_activity = None
    _idle_timeout = 3600  # seconds (1 minute default)
    _cleanup_task = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_browser(self):
        if self._browser is None:
            self._playwright = await async_playwright().start()
            import os
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            self._browser = await self._playwright.chromium.launch(headless=False, downloads_path=downloads_path)
            self._start_idle_monitor()
        self._update_activity()
        return self._browser

    async def create_page(self, page_title: str):
        browser = await self.get_browser()
        page = await browser.new_page(viewport={'width': 1366, 'height': 768})
        self._pages[page_title] = page
        self._update_activity()
        return page

    def get_page(self, page_title: str):
        self._update_activity()
        return self._pages.get(page_title)

    def list_pages(self):
        return list(self._pages.keys())

    def _update_activity(self):
        """Update the last activity timestamp"""
        self._last_activity = datetime.now()

    def _start_idle_monitor(self):
        """Start background task to monitor idle timeout"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._idle_monitor())

    async def _idle_monitor(self):
        """Monitor browser activity and close if idle for too long"""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds

            if self._browser is not None and self._last_activity is not None:
                idle_time = (datetime.now() - self._last_activity).total_seconds()

                if idle_time >= self._idle_timeout:
                    await self._close_browser()
                    break

    async def _close_browser(self):
        """Close browser and clean up resources"""
        if self._browser is not None:
            # Close all pages first
            for page in self._pages.values():
                try:
                    await page.close()
                except:
                    pass

            self._pages.clear()

            # Close browser
            try:
                await self._browser.close()
            except:
                pass

            # Stop playwright
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except:
                    pass

            self._browser = None
            self._playwright = None
            self._last_activity = None
            self._cleanup_task = None