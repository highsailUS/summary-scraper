# app/main.py
import re
import httpx
from typing import Optional
from bs4 import BeautifulSoup

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl

import os
SCRAPFLY_KEY = os.environ.get("SCRAPFLY_KEY")

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
    """
    Scrape Upwork SEO job page using ScrapFly (Cloudflare bypass + JS rendering).
    Returns clean <p> paragraphs inside job description.
    """

    api = "https://api.scrapfly.io/scrape"

    params = {
        "key": SCRAPFLY_KEY,
        "url": apply_url,
        "render_js": "true",  # loads job description reliably
    }

    async with httpx.AsyncClient(timeout=35) as client:
        res = await client.get(api, params=params)

    if res.status_code != 200:
        raise RuntimeError(f"ScrapFly request failed: {res.text}")

    try:
        html = res.json()["result"]["content"]
    except:
        raise RuntimeError("ScrapFly returned no content")

    soup = BeautifulSoup(html, "html.parser")

    # Extract job body paragraphs
    paragraphs = [
        p.get_text(strip=True)
        for p in soup.select("section[data-test='job-description-section'] p")
    ]

    if not paragraphs:
        raise RuntimeError("No job description found")

    return paragraphs


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
