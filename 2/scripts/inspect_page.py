import asyncio
import json
import re

import httpx
from bs4 import BeautifulSoup

from app.infrastructure.enrichment.page_fetcher import HttpPageFetcher


async def main() -> None:
    url = "https://www.digital-calendar.ru/digital_minsk_2026/"
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        html = response.text

    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.S | re.I,
    ):
        print("JSON-LD:", match.group(1)[:1200])

    soup = BeautifulSoup(html, "html.parser")
    for selector in ["time", "[datetime]", "meta[property*='date']", "meta[itemprop*='date']"]:
        for element in soup.select(selector)[:8]:
            value = element.get("datetime") or element.get("content") or element.get_text(strip=True)
            print("ELEM", selector, value[:120] if value else None)

    fetcher = HttpPageFetcher()
    page = await fetcher.fetch(url)
    print("--- EXTRACTED TEXT (first 2500 chars) ---")
    print(page.text[:2500])


if __name__ == "__main__":
    asyncio.run(main())
