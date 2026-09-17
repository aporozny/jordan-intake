import asyncio
from typing import Optional
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def scrape_url_to_markdown(url: str, max_chars: int = 5000) -> Optional[str]:
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        remove_overlay_elements=True
    )
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            if result.success and result.markdown:
                return result.markdown[:max_chars].strip()
            return None
    except Exception as e:
        print(f["scraper_error: {e}"])
        return None

def fetch_page_sync(url: str, max_chars: int = 5000) -> Optional[str]:
    return asyncio.run(scrape_url_to_markdown(url, max_chars=max_chars))

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(f"Sequencing scrape for {url}...")
    res = fetch_page_sync(url)
    print("--- OUTPUT ---")
    print(res)
