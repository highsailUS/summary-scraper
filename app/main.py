# app/main.py
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from playwright.async_api import async_playwright

app = FastAPI(title="Upwork Summary Scraper")

# ---------- Models ----------

class UpworkSummaryRequest(BaseModel):
    apply_url: AnyHttpUrl
    job_id: Optional[str] = None


class UpworkSummaryResponse(BaseModel):
    job_id: Optional[str]
    apply_url: AnyHttpUrl
    summary: str
    paragraphs: list[str]


# ---------- Core scraper ----------

async def fetch_upwork_summary(apply_url: str) -> list[str]:
    """
    Open the Upwork SEO/apply URL and extract all job description paragraphs.
    Includes Railway-safe Chromium flags + Cloudflare bypass delays + hydration waits.
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--single-process",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )

        # Stealth tweaks
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = await context.new_page()

        try:
            # Upwork often delays hydration — we allow more time but enforce hard caps
            await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)

            # Additional wait to bypass Cloudflare's bot checks
            await page.wait_for_timeout(1500)

            # The standard selector
            selector = "section[data-test='job-description-section']"

            await page.wait_for_selector(selector, timeout=30000)

            # Try primary targeted <p> tags first
            para_locator = page.locator(
                f"{selector} p.text-body-sm"
            )
            count = await para_locator.count()

            # Fallback to ANY paragraph in the description section
            if count == 0:
                para_locator = page.locator(f"{selector} p")
                count = await para_locator.count()

            # If still nothing, render fully and try again
            if count == 0:
                await page.wait_for_timeout(1500)
                para_locator = page.locator(f"{selector} p")
                count = await para_locator.count()

            if count == 0:
                raise RuntimeError("No paragraphs found in description section")

            paragraphs: list[str] = []
            for i in range(count):
                text = (await para_locator.nth(i).inner_text()).strip()
                if text:
                    paragraphs.append(text)

            return paragraphs

        finally:
            await context.close()
            await browser.close()


# ---------- API routes ----------

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
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")

    summary = "\n\n".join(paragraphs)

    return UpworkSummaryResponse(
        job_id=payload.job_id,
        apply_url=payload.apply_url,
        summary=summary,
        paragraphs=paragraphs,
    )
