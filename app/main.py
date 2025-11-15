import re
import requests
from typing import Optional, List

from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl

app = FastAPI(title="Upwork Summary Scraper (Ultra Simple)")


class UpworkSummaryRequest(BaseModel):
    apply_url: AnyHttpUrl
    job_id: Optional[str] = None


class UpworkSummaryResponse(BaseModel):
    job_id: Optional[str]
    apply_url: AnyHttpUrl
    summary: str
    paragraphs: List[str]


def fetch_upwork_summary(url: str) -> List[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    r = requests.get(url, headers=headers, timeout=15)

    if r.status_code != 200:
        raise HTTPException(500, f"Failed to load page: {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")

    # Upwork renders description inside <div data-test="description">
    desc = soup.select_one("div[data-test='description']")

    if desc is None:
        raise RuntimeError("Description section not found")

    paragraphs = []

    for p in desc.find_all("p"):
        clean = p.get_text(strip=True)
        if clean:
            paragraphs.append(clean)

    if not paragraphs:
        raise RuntimeError("No paragraphs found in description")

    return paragraphs


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@app.post("/upwork-summary", response_model=UpworkSummaryResponse)
async def upwork_summary(payload: UpworkSummaryRequest):
    try:
        paragraphs = fetch_upwork_summary(str(payload.apply_url))
    except Exception as e:
        raise HTTPException(500, f"Scrape failed: {e}")

    summary = "\n\n".join(paragraphs)

    return UpworkSummaryResponse(
        job_id=payload.job_id,
        apply_url=payload.apply_url,
        summary=summary,
        paragraphs=paragraphs,
    )
