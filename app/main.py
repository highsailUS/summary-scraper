# app/main.py
import re
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


# ---------- Core Scraper (Railway-optimized) ----------

async def fetch_upwork_summary(apply_url: str) -> list[str]:
    """
    Fast Upwork scraper using static HTML (JS disabled).
    Works on Railway without hanging or timing out.
    """

    async with async_playwright() as p:
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
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            java_script_enabled=False,     # 🚀 KEY: forces fast SSR HTML
        )

        page = await context.new_page()

        try:
            # Fast load: no hydration, no JS scripts
            await page.goto(
                apply_url,
                wait_until="networkidle",
                timeout=15000,  # 15 sec hard limit (Railway safe)
            )

            html = await page.content()

            # Extract all <p> paragraphs (SSR HTML contains them)
            raw_paras = re.findall(
                r"<p[^>]*>(.*?)</p>",
                html,
                flags=re.DOTALL | re.IGNORECASE
            )

            paragraphs = []
            for ptag in raw_paras:
                clean = re.sub(r"<.*?>", "", ptag).strip()
                if clean:
                    paragraphs.append(clean)

            if not paragraphs:
                raise RuntimeError("No paragraphs found in SSR HTML")

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
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")

    summary = "\n\n".join(paragraphs)

    return UpworkSummaryResponse(
        job_id=payload.job_id,
        apply_url=payload.apply_url,
        summary=summary,
        paragraphs=paragraphs,
    )
