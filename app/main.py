# app/main.py
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl

app = FastAPI(title="Upwork Summary Scraper")


class UpworkSummaryRequest(BaseModel):
    apply_url: AnyHttpUrl
    job_id: Optional[str] = None


class UpworkSummaryResponse(BaseModel):
    job_id: Optional[str]
    apply_url: AnyHttpUrl
    summary: str
    paragraphs: list[str]


async def fetch_upwork_summary(apply_url: str) -> list[str]:
    # undetected_playwright launcher
    browser = await up.chromium.launch(
        headless=True,
        no_sandbox=True,
    )

    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
    )

    page = await context.new_page()

    try:
        await page.goto(apply_url, wait_until="load", timeout=45000)

        # Wait for description section to actually render
        await page.wait_for_selector(
            "section[data-test='job-description-section']",
            timeout=20000
        )

        html = await page.content()

        # scrape <p> tags inside description
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
            raise RuntimeError("No paragraphs found in job description")

        return paragraphs

    finally:
        await context.close()
        await browser.close()


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


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
