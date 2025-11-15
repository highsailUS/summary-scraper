# Upwork Summary Scraper (Railway + Playwright)

Scrapes the **full job summary** from an Upwork SEO/apply URL and returns it via a FastAPI endpoint.

## API

### Health check

GET `/healthz`

Returns:

```json
{ "status": "ok" }
