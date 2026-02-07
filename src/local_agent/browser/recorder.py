import asyncio

from playwright.async_api import Page

from local_agent.utils.logging import logger

# JavaScript injected into the page to capture user interactions.
# Events are stored in window.__recorder.events and flushed by Python polling.
RECORDER_JS = """
(() => {
    if (window.__recorder) return;

    window.__recorder = { events: [], lastInputValues: {} };
    const rec = window.__recorder;

    function getOwnText(el) {
        // Get only direct text of element, not children's text
        let text = '';
        for (const node of el.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                text += node.textContent.trim();
            }
        }
        return text.substring(0, 60);
    }

    function getScreenRegion(x, y) {
        const w = window.innerWidth;
        const h = window.innerHeight;
        const col = x < w * 0.25 ? 'left' : x > w * 0.75 ? 'right' : 'center';
        const row = y < h * 0.3 ? 'top' : y > h * 0.7 ? 'bottom' : 'middle';
        return row + '-' + col;
    }

    function elementInfo(el) {
        if (!el || !el.tagName) return {};
        const info = { tag: el.tagName.toLowerCase() };

        // Get own text first (not children), fall back to textContent for small elements
        const ownText = getOwnText(el);
        const fullText = (el.textContent || '').trim();
        if (ownText) {
            info.text = ownText;
        } else if (fullText.length <= 40) {
            info.text = fullText;
        }

        // Standard attributes
        if (el.getAttribute('aria-label'))
            info.aria_label = el.getAttribute('aria-label');
        if (el.getAttribute('placeholder'))
            info.placeholder = el.getAttribute('placeholder');
        if (el.getAttribute('role'))
            info.role = el.getAttribute('role');
        if (el.getAttribute('name'))
            info.name = el.getAttribute('name');
        if (el.getAttribute('type'))
            info.input_type = el.getAttribute('type');
        if (el.getAttribute('data-tooltip'))
            info.tooltip = el.getAttribute('data-tooltip');
        if (el.getAttribute('title'))
            info.title = el.getAttribute('title');

        // Check if contenteditable (Gmail compose fields etc)
        if (el.getAttribute('contenteditable') === 'true' || el.isContentEditable)
            info.contenteditable = true;

        // Parent context — helps identify where on the page
        const parent = el.closest('[aria-label], [role="navigation"], [role="banner"], [role="main"], [role="complementary"], nav, header, aside, main');
        if (parent && parent !== el) {
            const parentLabel = parent.getAttribute('aria-label') || parent.getAttribute('role') || parent.tagName.toLowerCase();
            if (parentLabel) info.parent_context = parentLabel.substring(0, 50);
        }

        // Nearby label — for input fields
        if (el.id) {
            const label = document.querySelector('label[for="' + el.id + '"]');
            if (label) info.label = label.textContent.trim().substring(0, 40);
        }

        return info;
    }

    // Capture clicks (mousedown for accuracy)
    document.addEventListener('mousedown', (e) => {
        rec.events.push({
            type: 'click',
            x: Math.round(e.clientX),
            y: Math.round(e.clientY),
            region: getScreenRegion(e.clientX, e.clientY),
            timestamp: Date.now(),
            element: elementInfo(e.target),
            page_title: document.title
        });
    }, true);

    // Capture text input — supports both <input> and contenteditable
    document.addEventListener('change', (e) => {
        const el = e.target;
        if (el.tagName && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')) {
            rec.events.push({
                type: 'type',
                text: el.value,
                timestamp: Date.now(),
                element: elementInfo(el)
            });
        }
    }, true);

    // Track typing in real-time (debounced) — also contenteditable
    let inputTimer = null;
    document.addEventListener('input', (e) => {
        const el = e.target;
        if (!el.tagName) return;
        const tag = el.tagName;
        const isEditable = el.isContentEditable;

        if (tag !== 'INPUT' && tag !== 'TEXTAREA' && !isEditable) return;

        const value = isEditable ? (el.innerText || '').trim() : el.value;
        const key = el.getAttribute('aria-label') || el.getAttribute('name') || el.getAttribute('placeholder') || el.getAttribute('role') || 'unknown';

        rec.lastInputValues[key] = { value, timestamp: Date.now(), element: elementInfo(el) };

        clearTimeout(inputTimer);
        inputTimer = setTimeout(() => {
            for (const [k, v] of Object.entries(rec.lastInputValues)) {
                rec.events.push({
                    type: 'type',
                    text: v.value,
                    timestamp: v.timestamp,
                    element: v.element
                });
            }
            rec.lastInputValues = {};
        }, 1000);
    }, true);

    // Capture special key presses (Enter, Tab, Escape)
    document.addEventListener('keydown', (e) => {
        const special = ['Enter', 'Tab', 'Escape', 'Backspace', 'Delete'];
        if (special.includes(e.key)) {
            rec.events.push({
                type: 'key',
                key: e.key,
                timestamp: Date.now(),
                element: elementInfo(e.target)
            });
        }
    }, true);
})();
"""

FLUSH_JS = """
(() => {
    if (!window.__recorder) return [];
    const events = window.__recorder.events.splice(0);

    // Also flush any pending debounced input
    for (const [k, v] of Object.entries(window.__recorder.lastInputValues)) {
        events.push({
            type: 'type',
            text: v.value,
            timestamp: v.timestamp,
            element: v.element
        });
    }
    window.__recorder.lastInputValues = {};

    return events;
})()
"""


class BrowserRecorder:
    """Records user interactions in the browser via injected JavaScript."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._poll_task: asyncio.Task | None = None
        self._events: list[dict] = []
        self._running = False
        self._last_url: str = ""

    @property
    def is_recording(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Inject recording JS and start polling for events."""
        self._events = []
        self._running = True
        self._last_url = self._page.url

        await self._inject()
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Recording started on %s", self._last_url)

    async def stop(self) -> list[dict]:
        """Stop recording and return all captured events."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        # Final flush
        await self._flush()

        events = self._events.copy()
        self._events = []
        logger.info("Recording stopped — %d raw events captured", len(events))
        return events

    async def _inject(self) -> None:
        """Inject the recorder script into the current page."""
        try:
            await self._page.evaluate(RECORDER_JS)
            logger.debug("Recorder JS injected into %s", self._page.url)
        except Exception as e:
            logger.warning("Failed to inject recorder JS: %s", e)

    async def _flush(self) -> None:
        """Flush events from the browser to Python."""
        try:
            new_events = await self._page.evaluate(FLUSH_JS)
            if new_events:
                self._events.extend(new_events)
        except Exception as e:
            logger.debug("Flush failed (page may have navigated): %s", e)

    async def _poll_loop(self) -> None:
        """Poll for events and detect navigation."""
        while self._running:
            await asyncio.sleep(0.5)

            if not self._running:
                break

            # Detect navigation — re-inject if URL changed
            current_url = self._page.url
            if current_url != self._last_url:
                logger.info("Navigation detected: %s → %s", self._last_url, current_url)
                self._events.append({
                    "type": "navigate",
                    "url": current_url,
                    "timestamp": int(asyncio.get_event_loop().time() * 1000),
                })
                self._last_url = current_url
                # Re-inject after navigation
                await asyncio.sleep(0.5)  # Wait for page to settle
                await self._inject()
                continue

            # Normal flush
            await self._flush()
