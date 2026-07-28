"""A real browser, behind the computer port.

The browser is the 90% case for computer control — research, forms,
dashboards, anything with a login — and unlike a desktop it can be contained:
its own profile, its own download directory, no access to the filesystem
outside the workspace.

Perception is an **element index built from the accessibility tree**, not a
screenshot the model has to squint at. Each interactive element gets a
per-snapshot ref bound to a live Playwright handle, so acting on `e7` is exact
where clicking a coordinate is a guess about what has not moved since the
screenshot. The screenshot is still captured, as evidence for the audit log
and for the human being asked to approve something.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from jarvis.computer.models import Action, ActionKind, ActionResult, Element, Snapshot
from jarvis.computer.policy import looks_secret

if TYPE_CHECKING:  # pragma: no cover - import cost only
    from playwright.async_api import ElementHandle, Page

log = structlog.get_logger(__name__)

MAX_ELEMENTS = 120
MAX_TEXT_CHARS = 6_000
ACTION_TIMEOUT_MS = 15_000

# Selector for things a person could interact with. Deliberately narrow: an
# index of 400 divs is not perception, it is noise the model has to wade past.
INTERACTIVE = (
    "a[href], button, input:not([type=hidden]), select, textarea, "
    "[role=button], [role=link], [role=textbox], [role=checkbox], [role=tab], [contenteditable]"
)


class PlaywrightComputer:
    """Chromium, driven through the accessibility tree."""

    name = "browser"

    def __init__(
        self,
        *,
        headless: bool = True,
        executable_path: str | None = None,
        downloads: Path | None = None,
        viewport: tuple[int, int] = (1280, 900),
    ) -> None:
        self._headless = headless
        self._executable_path = executable_path
        self._downloads = downloads
        self._viewport = viewport
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Page | None = None
        self._handles: dict[str, ElementHandle] = {}

    def is_available(self) -> bool:
        try:
            import playwright.async_api  # noqa: F401
        except ImportError:
            return False
        return True

    async def start(self) -> None:
        if self._page is not None:
            return
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch: dict[str, Any] = {"headless": self._headless}
        if self._executable_path:
            launch["executable_path"] = self._executable_path
        self._browser = await self._playwright.chromium.launch(**launch)

        context = await self._browser.new_context(
            viewport={"width": self._viewport[0], "height": self._viewport[1]},
            accept_downloads=self._downloads is not None,
        )
        self._page = await context.new_page()
        self._page.set_default_timeout(ACTION_TIMEOUT_MS)
        log.info("browser.started", headless=self._headless)

    async def stop(self) -> None:
        self._handles.clear()
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("browser not started")
        return self._page

    # ── Perception ────────────────────────────────────────────────────────────

    async def observe(self) -> Snapshot:
        page = self._require_page()
        self._handles.clear()

        elements: list[Element] = []
        for index, handle in enumerate(await page.query_selector_all(INTERACTIVE)):
            if len(elements) >= MAX_ELEMENTS:
                break
            element = await self._describe(handle, f"e{index + 1}")
            if element is None:
                continue
            self._handles[element.ref] = handle
            elements.append(element)

        try:
            text = await page.inner_text("body")
        except Exception:
            text = ""

        return Snapshot(
            url=page.url,
            title=await page.title(),
            text=text[:MAX_TEXT_CHARS],
            elements=elements,
            screenshot=await page.screenshot(type="png"),
        )

    async def _describe(self, handle: ElementHandle, ref: str) -> Element | None:
        """Turn a DOM handle into an element, or None if it is not perceivable."""
        try:
            if not await handle.is_visible():
                return None
            tag = (await handle.evaluate("e => e.tagName")).lower()
            input_type = (await handle.get_attribute("type") or "").lower()
            role = await handle.get_attribute("role") or _role_for(tag, input_type)

            name = (
                await handle.get_attribute("aria-label")
                or (await handle.inner_text() or "").strip()
                or await handle.get_attribute("placeholder")
                or await handle.get_attribute("name")
                or await handle.get_attribute("title")
                or await handle.get_attribute("alt")
                or ""
            )
            name = " ".join(name.split())[:120]

            value = ""
            if tag in ("input", "textarea", "select"):
                value = (await handle.input_value() if tag != "select" else "") or ""

            secret = looks_secret(
                # A field's identity is spread across several attributes and
                # sites are inconsistent about which one they use, so all of
                # them count towards the decision.
                " ".join(
                    filter(
                        None,
                        [
                            name,
                            await handle.get_attribute("name") or "",
                            await handle.get_attribute("id") or "",
                            await handle.get_attribute("autocomplete") or "",
                        ],
                    )
                ),
                input_type=input_type,
            )
            return Element(
                ref=ref,
                role=role,
                name=name,
                # Never surface the contents of a secret field, not even to the
                # model — the index is logged and shown in approval prompts.
                value="" if secret else value[:120],
                enabled=await handle.is_enabled(),
                secret=secret,
            )
        except Exception:  # pragma: no cover - a detached node during a re-render
            return None

    # ── Action ────────────────────────────────────────────────────────────────

    async def act(self, action: Action) -> ActionResult:
        page = self._require_page()
        detail = ""
        ok = True
        try:
            match action.kind:
                case ActionKind.NAVIGATE:
                    await page.goto(action.url, wait_until="domcontentloaded")
                case ActionKind.BACK:
                    await page.go_back(wait_until="domcontentloaded")
                case ActionKind.CLICK:
                    await self._handle(action.ref).click()
                    await self._settle()
                case ActionKind.TYPE:
                    handle = self._handle(action.ref)
                    await handle.fill("")
                    await handle.type(action.text, delay=12)
                    detail = f"entered {len(action.text)} characters"
                case ActionKind.SELECT:
                    await self._handle(action.ref).select_option(label=action.text)
                case ActionKind.PRESS:
                    await self._handle(action.ref).press(action.key)
                    await self._settle()
                case ActionKind.SCROLL:
                    await page.mouse.wheel(0, action.amount or 600)
                case ActionKind.WAIT:
                    await page.wait_for_timeout(min(max(action.amount, 100), 5_000))
        except Exception as exc:
            ok = False
            detail = str(exc).splitlines()[0][:300]
            log.warning("computer.action_failed", kind=action.kind.value, error=detail)

        return ActionResult(action=action, ok=ok, snapshot=await self.observe(), detail=detail)

    async def _settle(self) -> None:
        """Give a click somewhere to land, without hanging on a chatty page."""
        with contextlib.suppress(Exception):
            await self._require_page().wait_for_load_state("networkidle", timeout=3_000)

    def _handle(self, ref: str) -> ElementHandle:
        try:
            return self._handles[ref]
        except KeyError:
            raise RuntimeError(f"no element {ref!r} in the last observation") from None


def _role_for(tag: str, input_type: str) -> str:
    if tag == "a":
        return "link"
    if tag == "button" or input_type in ("submit", "button"):
        return "button"
    if tag == "select":
        return "select"
    if input_type == "checkbox":
        return "checkbox"
    if tag in ("input", "textarea"):
        return "textbox"
    return tag
