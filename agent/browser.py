import os
import asyncio
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Download

class BrowserManager:
    """Encapsulates Playwright Chromium automation, DOM numbering snapshots, and screenshots."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.element_map: Dict[int, str] = {}

    async def start(self):
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()
            if not self.browser:
                self.browser = await self.playwright.chromium.launch(headless=self.headless)
            if not self.context:
                self.context = await self.browser.new_context(accept_downloads=True)
            if not self.page or self.page.is_closed():
                self.page = await self.context.new_page()
        except Exception as e:
            await self.close()
            raise RuntimeError(f"Failed to launch browser/page: {str(e)}")

    async def close(self):
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    async def goto(self, url: str) -> Dict[str, Any]:
        try:
            await self.start()
            if not self.page:
                return {"ok": False, "error_type": "BrowserError", "message": "Browser page is not available."}
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            return {"ok": True, "message": f"Navigated to {url}"}
        except Exception as e:
            return {"ok": False, "error_type": "NavigationError", "message": f"Failed to navigate to {url}: {str(e)}"}

    async def get_snapshot(self, run_dir: Optional[str] = None, step_num: int = 0) -> Dict[str, Any]:
        try:
            await self.start()
        except Exception as e:
            return {
                "url": "",
                "title": "Browser Launch Error",
                "visible_text": f"Failed to launch browser: {str(e)}",
                "elements": [],
                "observation": f"Browser launch error: {str(e)}",
                "screenshot_path": ""
            }
        if not self.page:
            return {
                "url": "",
                "title": "Browser Page Error",
                "visible_text": "Browser page is unavailable.",
                "elements": [],
                "observation": "Browser page is unavailable.",
                "screenshot_path": ""
            }
        js_script = """
        () => {
            document.querySelectorAll('[data-agent-id]').forEach(el => el.removeAttribute('data-agent-id'));
            const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
            const elements = Array.from(document.querySelectorAll(interactiveSelectors));
            
            let counter = 1;
            const items = [];

            for (const el of elements) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;

                el.setAttribute('data-agent-id', counter.toString());
                
                let tag = el.tagName.toLowerCase();
                let type = el.getAttribute('type') || '';
                let name = el.getAttribute('name') || '';
                let id = el.getAttribute('id') || '';
                let placeholder = el.getAttribute('placeholder') || '';
                let text = (el.innerText || el.value || placeholder || '').trim().replace(/\\s+/g, ' ');
                if (text.length > 50) text = text.substring(0, 50) + '...';

                let desc = `[${counter}] <${tag}`;
                if (type) desc += ` type="${type}"`;
                if (name) desc += ` name="${name}"`;
                if (id) desc += ` id="${id}"`;
                if (placeholder) desc += ` placeholder="${placeholder}"`;
                desc += `>`;
                if (text) desc += ` text="${text}"`;

                items.push({
                    id: counter,
                    description: desc,
                    tag: tag,
                    text: text
                });
                counter++;
            }

            let visibleText = document.body ? document.body.innerText.replace(/\\s+/g, ' ').trim() : '';
            if (visibleText.length > 3000) {
                visibleText = visibleText.substring(0, 3000) + '... [trimmed]';
            }

            return {
                url: window.location.href,
                title: document.title,
                visible_text: visibleText,
                elements: items
            };
        }
        """
        snapshot_data = await self.page.evaluate(js_script)
        
        screenshot_path = ""
        if run_dir:
            os.makedirs(run_dir, exist_ok=True)
            screenshot_path = os.path.join(run_dir, f"step_{step_num:02d}.png")
            await self.page.screenshot(path=screenshot_path)

        elements_formatted = "\n".join([item["description"] for item in snapshot_data["elements"]])
        
        obs_text = (
            f"URL: {snapshot_data['url']}\n"
            f"Title: {snapshot_data['title']}\n"
            f"Visible Page Content:\n{snapshot_data['visible_text']}\n\n"
            f"Interactive Elements:\n{elements_formatted if elements_formatted else '(No interactive elements found)'}"
        )

        return {
            "url": snapshot_data["url"],
            "title": snapshot_data["title"],
            "visible_text": snapshot_data["visible_text"],
            "elements": snapshot_data["elements"],
            "observation": obs_text,
            "screenshot_path": screenshot_path
        }

    async def click(self, element_id: int) -> Dict[str, Any]:
        await self.start()
        selector = f"[data-agent-id='{element_id}']"
        try:
            el = await self.page.query_selector(selector)
            if not el:
                return {"ok": False, "error_type": "ElementNotFound", "message": f"Element [{element_id}] not found on current page."}
            
            # Check element metadata for approval verification
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            el_type = await el.evaluate("el => el.getAttribute('type') || ''")
            el_text = await el.evaluate("el => (el.innerText || el.value || '').trim()")
            is_submit_action = (tag == "button" and el_type == "submit") or "submit" in el_text.lower() or "confirm" in el_text.lower()

            await el.click(timeout=10000)
            await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            return {"ok": True, "message": f"Clicked element [{element_id}] ({tag})", "is_submit_action": is_submit_action}
        except Exception as e:
            return {"ok": False, "error_type": "ActionFailed", "message": f"Failed to click element [{element_id}]: {str(e)}"}

    async def fill(self, element_id: int, value: str) -> Dict[str, Any]:
        await self.start()
        selector = f"[data-agent-id='{element_id}']"
        try:
            el = await self.page.query_selector(selector)
            if not el:
                return {"ok": False, "error_type": "ElementNotFound", "message": f"Element [{element_id}] not found on current page."}
            await el.fill(value, timeout=10000)
            return {"ok": True, "message": f"Filled element [{element_id}] with value '{value}'"}
        except Exception as e:
            return {"ok": False, "error_type": "ActionFailed", "message": f"Failed to fill element [{element_id}]: {str(e)}"}

    async def select_option(self, element_id: int, value: str) -> Dict[str, Any]:
        await self.start()
        selector = f"[data-agent-id='{element_id}']"
        try:
            el = await self.page.query_selector(selector)
            if not el:
                return {"ok": False, "error_type": "ElementNotFound", "message": f"Element [{element_id}] not found on current page."}
            await el.select_option(value=value, timeout=10000)
            return {"ok": True, "message": f"Selected option '{value}' on element [{element_id}]"}
        except Exception as e:
            return {"ok": False, "error_type": "ActionFailed", "message": f"Failed to select option on element [{element_id}]: {str(e)}"}

    async def download_file(self, element_id: int, save_dir: str) -> Dict[str, Any]:
        await self.start()
        selector = f"[data-agent-id='{element_id}']"
        os.makedirs(save_dir, exist_ok=True)
        try:
            el = await self.page.query_selector(selector)
            if not el:
                return {"ok": False, "error_type": "ElementNotFound", "message": f"Element [{element_id}] not found on page."}
            
            async with self.page.expect_download(timeout=15000) as download_info:
                await el.click()
            download: Download = await download_info.value
            
            save_path = os.path.join(save_dir, download.suggested_filename)
            await download.save_as(save_path)
            return {"ok": True, "message": f"Downloaded file to {save_path}", "file_path": save_path}
        except Exception as e:
            return {"ok": False, "error_type": "DownloadFailed", "message": f"Failed download on element [{element_id}]: {str(e)}"}
