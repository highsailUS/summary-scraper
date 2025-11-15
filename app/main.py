import os
import re
from playwright.async_api import async_playwright

async def fetch_upwork_summary(apply_url: str) -> list[str]:
    MASTER = os.getenv("UPWORK_MASTER_ACCESS_TOKEN")
    GLOBAL = os.getenv("UPWORK_GLOBAL_JS_TOKEN")

    if not MASTER or not GLOBAL:
        raise RuntimeError("Missing Upwork cookie env vars")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
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

        # 🚀 IMPORTANT — add Upwork cookies
        await context.add_cookies([
            {
                "name": "master_access_token",
                "value": MASTER,
                "domain": ".upwork.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            },
            {
                "name": "oauth2_global_js_token",
                "value": GLOBAL,
                "domain": ".upwork.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            },
        ])

        page = await context.new_page()

        await page.goto(apply_url, wait_until="domcontentloaded", timeout=45000)

        # wait for job description
        try:
            await page.wait_for_selector(
                "section[data-test='job-description-section']",
                timeout=15000
            )
        except:
            html = await page.content()
            raise RuntimeError("Job description not found - blocked or cookies invalid")

        html = await page.content()

        # Extract <p> content
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
            raise RuntimeError("No job description paragraphs found")

        await browser.close()
        return paragraphs
