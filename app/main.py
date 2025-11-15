# app/main.py
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Upwork Internal Job Scraper")

# Load cookies from environment variables
MASTER_ACCESS = os.getenv("UPWORK_MASTER_ACCESS_TOKEN")
GLOBAL_JS = os.getenv("UPWORK_GLOBAL_JS_TOKEN")

if not MASTER_ACCESS or not GLOBAL_JS:
    raise RuntimeError("Missing Upwork cookie env vars")

class JobRequest(BaseModel):
    job_id: str

class JobResponse(BaseModel):
    job_id: str
    title: str | None
    description_html: str | None
    description_text: str | None
    raw: dict

UPWORK_ENDPOINT = "https://www.upwork.com/nx/jobs/{job_id}/details"

COMMON_HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",

    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.upwork.com",
    "Referer": "https://www.upwork.com/",
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

def get_cookie_header():
    return f"master_access_token={MASTER_ACCESS}; oauth2_global_js_token={GLOBAL_JS};"

@app.post("/scrape", response_model=JobResponse)
async def scrape_job(request: JobRequest):
    url = UPWORK_ENDPOINT.format(job_id=request.job_id)

    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        try:
            r = await client.get(
                url,
                headers={**COMMON_HEADERS, "Cookie": get_cookie_header()},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upwork request failed: {e}")

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code,
                            detail=f"Upwork returned {r.status_code}: {r.text}")

    data = r.json()

    # Extract description if present
    title = data.get("title")
    desc_html = data.get("description")
    desc_text = desc_html.replace("<br />", "\n").replace("<p>", "").replace("</p>", "").strip() if desc_html else None

    return JobResponse(
        job_id=request.job_id,
        title=title,
        description_html=desc_html,
        description_text=desc_text,
        raw=data,
    )

@app.get("/healthz")
def health():
    return {"status": "ok"}
