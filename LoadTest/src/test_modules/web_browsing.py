from dataclasses import dataclass
from playwright.sync_api import sync_playwright


@dataclass
class WebBrowsingResult:
    url: str
    page_load_time: float      # ms
    ttfb: float                # ms (time to first byte)
    dom_content_loaded: float  # ms
    http_response_code: int
    resource_count: int
    redirect_count: int


def run_web_browsing_test(parameters: dict) -> list[WebBrowsingResult]:
    """
    Run web browsing tests using Playwright.

    Args:
        parameters: dict with 'target_url' (list of URLs) and 'headless' (bool)

    Returns:
        List of WebBrowsingResult for each URL
    """
    target_urls = parameters.get("target_url", [])
    headless = parameters.get("headless", True)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()

        for url in target_urls:
            result = _load_page(context, url)
            results.append(result)

        browser.close()

    return results


def _load_page(context, url: str) -> WebBrowsingResult:
    """Load a single page and collect metrics."""
    page = context.new_page()

    resource_count = 0
    redirect_count = 0
    http_response_code = 0

    def on_response(response):
        nonlocal resource_count, redirect_count, http_response_code
        resource_count += 1
        if response.url == url or response.url == page.url:
            http_response_code = response.status
        if 300 <= response.status < 400:
            redirect_count += 1

    page.on("response", on_response)

    try:
        response = page.goto(url, wait_until="load")
        if response:
            http_response_code = response.status

        timing = page.evaluate("""() => {
            const perf = performance.getEntriesByType('navigation')[0];
            return {
                page_load_time: perf.loadEventEnd - perf.startTime,
                ttfb: perf.responseStart - perf.requestStart,
                dom_content_loaded: perf.domContentLoadedEventEnd - perf.startTime
            };
        }""")

        result = WebBrowsingResult(
            url=url,
            page_load_time=timing.get("page_load_time", 0),
            ttfb=timing.get("ttfb", 0),
            dom_content_loaded=timing.get("dom_content_loaded", 0),
            http_response_code=http_response_code,
            resource_count=resource_count,
            redirect_count=redirect_count
        )
    except Exception:
        result = WebBrowsingResult(
            url=url,
            page_load_time=0,
            ttfb=0,
            dom_content_loaded=0,
            http_response_code=0,
            resource_count=resource_count,
            redirect_count=redirect_count
        )
    finally:
        page.close()

    return result

if __name__ == "__main__":
    params = {"target_url" : ["https://www.google.com","https://www.youtube.com"], "headless": True}
    results = run_web_browsing_test(parameters=params)
    print(results)
    