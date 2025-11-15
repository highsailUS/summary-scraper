# app/main.py
import os
import random
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

app = FastAPI(title="Upwork Summary Scraper")


# ---------- Models ----------

class UpworkSummaryRequest(BaseModel):
    apply_url: AnyHttpUrl
    job_id: Optional[str] = None


class UpworkSummaryResponse(BaseModel):
    job_id: Optional[str]
    apply_url: AnyHttpUrl
    summary: str
    paragraphs: List[str]


# ---------- Proxy Helpers ----------

def pick_random_proxy() -> Optional[dict]:
    """
    Read PROXIES env var and return a random proxy config for Playwright.
    Format (comma-separated):
      http://user:pass@host:port, http://user:pass@host2:port2
    If PROXIES is empty, return None (no proxy).
    """
    proxies_raw = os.getenv("PROXIES", "").strip()
    if not proxies_raw:
        return None

    proxy_strings = [p.strip() for p in proxies_raw.split(",") if p.strip()]
    if not proxy_strings:
        return None

    proxy_url = random.choice(proxy_strings)

    # Playwright supports simple {"server": "...", "username": "...", "password": "..."}
    # We'll just forward the full URL as server; most providers accept this.
    return {"server": proxy_url}


# ---------- Core Scraper ----------

async def fetch_upwork_summary(apply_url: str) -> List[str]:
    """
    Upwork scraper with:
    - JS enabled (Cloudflare happy)
    - Optional residential/mobile proxy (if PROXIES is set)
    - DOM-based extraction from description section
    """

    async with async_playwright() as p:
        proxy_cfg = pick_random_proxy()

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--single-process",
            ],
            proxy=proxy_cfg if proxy_cfg else None,
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            java_script_enabled=True,
            viewport={"width": 1280, "height": 900},
        )

        # Light stealth tweaks
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = await context.new_page()

        try:
            # Go to page and let JS run so Cloudflare is satisfied
            await page.goto(
                apply_url,
                wait_until="domcontentloaded",
                timeout=25000,
            )

            # Wait for the job description section if possible
            try:
                await page.wait_for_selector(
                    "section[data-test='job-description-section']",
                    timeout=15000,
                )
            except PlaywrightTimeoutError:
                # If we can't see the section, grab whole HTML and see if it's a Cloudflare page
                html = await page.content()
                if "Cloudflare Ray ID" in html or "Access denied" in html:
                    raise RuntimeError("Blocked by Cloudflare / WAF")
                else:
                    raise RuntimeError("Job description section not found")

            # Try paragraphs inside description section
            para_locator = page.locator(
                "section[data-test='job-description-section'] p"
            )
            count = await para_locator.count()

            paragraphs: List[str] = []
            for i in range(count):
                text = (await para_locator.nth(i).inner_text()).strip()
                if text:
                    paragraphs.append(text)

            # Fallback: if nothing found, at least try all <p> on page
            if not paragraphs:
                all_p = page.locator("p")
                total = await all_p.count()
                for i in range(total):
                    text = (await all_p.nth(i).inner_text()).strip()
                    if text:
                        paragraphs.append(text)

            if not paragraphs:
                raise RuntimeError("No job description paragraphs found")

            # Optional: strip obvious Cloudflare noise if we ever see it
            paragraphs = [
                p for p in paragraphs
                if "Cloudflare Ray ID" not in p and "Your IP:" not in p
            ]

            if not paragraphs:
                raise RuntimeError("Only Cloudflare content found")

            return paragraphs

        finally:
            await context.close()
            await browser.close()


# ---------- API Routes ----------

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@app.get("/ping")
async def ping():
    return {"pong": True}


@app.post("/upwork-summary", response_model=UpworkSummaryResponse)
async def upwork_summary(payload: UpworkSummaryRequest):
    try:
        paragraphs = await fetch_upwork_summary(str(payload.apply_url))
    except Exception as e:
        # In production you might log e here
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")

    summary = "\n\n".join(paragraphs)

    return UpworkSummaryResponse(
        job_id=payload.job_id,
        apply_url=payload.apply_url,
        summary=summary,
        paragraphs=paragraphs,
    )
