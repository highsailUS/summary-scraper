# app/main.py
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from playwright.async_api import async_playwright

app = FastAPI(title="Upwork Summary Scraper")

# ---------- Models ----------

class UpworkSummaryRequest(BaseModel):
    apply_url: AnyHttpUrl   # full SEO/apply URL
    job_id: Optional[str] = None  # optional, for convenience


class UpworkSummaryResponse(BaseModel):
    job_id: Optional[str]
    apply_url: AnyHttpUrl
    summary: str
    paragraphs: list[str]


# ---------- Core scraper ----------

async def fetch_upwork_summary(apply_url: str) -> list[str]:
    """
    Open the Upwork SEO/apply URL and return a list of text paragraphs
    from the job description section.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        # Realistic browser fingerprint
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        # Hide webdriver flag (light stealth)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        page = await context.new_page()

        try:
            await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)

            # Wait for description section to hydrate
            await page.wait_for_selector(
                "section[data-test='job-description-section']",
                timeout=30000,
            )

            # Primary selector – paragraphs in description section
            para_locator = page.locator(
                "section[data-test='job-description-section'] p.text-body-sm"
            )

            count = await para_locator.count()

            # Fallback: any <p> inside the description section
            if count == 0:
                para_locator = page.locator(
                    "section[data-test='job-description-section'] p"
                )
                count = await para_locator.count()

            if count == 0:
                raise RuntimeError("No description paragraphs found on page")

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


@app.post("/upwork-summary", response_model=UpworkSummaryResponse)
async def upwork_summary(payload: UpworkSummaryRequest):
    try:
        paragraphs = await fetch_upwork_summary(str(payload.apply_url))
    except Exception as e:
        # You can add logging here in production
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")

    summary = "\n\n".join(paragraphs)

    return UpworkSummaryResponse(
        job_id=payload.job_id,
        apply_url=payload.apply_url,
        summary=summary,
        paragraphs=paragraphs,
    )

