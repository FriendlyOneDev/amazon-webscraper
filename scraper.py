import re
import requests
import random
import time
import json
import os
import asyncio
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from datetime import datetime


class AmazonScraper:
    def __init__(self, output_dir="amazon_data"):
        self.user_agents = [
            "Mozilla/5.0 (iPad; CPU OS 8_4_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H321 Safari/600.1.4",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        ]
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
        }
        self.session = requests.Session()
        self.output_dir = output_dir

        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    async def get_page_async(self, url, attempt=1, max_attempts=3):
        """Fetch Amazon page with guaranteed price loading"""
        try:
            async with async_playwright() as p:
                # Configure browser to look more human-like
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        f"--user-agent={random.choice(self.user_agents)}",
                    ],
                )

                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800}, locale="en-US"
                )

                page = await context.new_page()

                # Block unnecessary resources
                await page.route(
                    "**/*.{png,jpg,jpeg,webp,gif,svg}", lambda route: route.abort()
                )
                await page.route("**/*.css", lambda route: route.abort())

                print(f"Fetching with Playwright (attempt {attempt}): {url}")

                try:
                    # Load page with networkidle state
                    await page.goto(url, timeout=30000, wait_until="networkidle")

                    # SPECIALIZED PRICE LOADING SEQUENCE
                    price_loaded = False
                    retries = 0
                    max_price_retries = 3

                    while not price_loaded and retries < max_price_retries:
                        # Scroll to trigger price loading
                        await page.evaluate("window.scrollBy(0, 500)")
                        await asyncio.sleep(1)

                        # Check for prices
                        price_elements = await page.query_selector_all("span.a-price")
                        if price_elements:
                            print(f"✅ Found {len(price_elements)} price elements")
                            price_loaded = True
                        else:
                            print("⚠️ No prices found, retrying...")
                            await asyncio.sleep(2)
                            retries += 1

                    if not price_loaded:
                        print("❌ Failed to load prices after retries")
                        await browser.close()

                        if attempt < max_attempts:
                            await asyncio.sleep(random.uniform(3, 7))
                            return await self.get_page_async(
                                url, attempt + 1, max_attempts
                            )
                        return None

                    # Get final content
                    html = await page.content()
                    await browser.close()
                    return type("Response", (), {"text": html, "status_code": 200})()

                except Exception as e:
                    print(f"Page error: {e}")
                    await browser.close()
                    if attempt < max_attempts:
                        await asyncio.sleep(random.uniform(3, 7))
                        return await self.get_page_async(url, attempt + 1, max_attempts)
                    return None

        except Exception as e:
            print(f"Browser error: {e}")
            return None

    def extract_product_blocks(self, soup):
        """Extract product blocks from search results page"""
        # Multiple selectors for different Amazon layouts
        block_selectors = [
            'div[data-component-type="s-search-result"]',
            "div[data-asin]",
            ".s-result-item[data-asin]",
            '[data-component-type="s-search-result"]',
        ]

        product_blocks = []
        for selector in block_selectors:
            blocks = soup.select(selector)
            if blocks:
                print(f"Found {len(blocks)} product blocks using selector: {selector}")
                product_blocks.extend(blocks)
                break

        # Remove duplicates based on data-asin if available
        seen_asins = set()
        unique_blocks = []

        for block in product_blocks:
            asin = block.get("data-asin")
            if asin:
                if asin not in seen_asins:
                    seen_asins.add(asin)
                    unique_blocks.append(block)
            else:
                unique_blocks.append(block)

        return unique_blocks

    async def get_search_results_async(self, query, pages=1, save_html=False):
        """Scrape multiple pages and return product block elements"""
        print(f"Starting search for: '{query}' across {pages} page(s)")

        all_blocks = []
        encoded_query = quote_plus(query)

        for page in range(1, pages + 1):
            print(f"\n--- Processing page {page} of {pages} ---")

            # Construct URL
            url = f"https://www.amazon.com/s?k={encoded_query}&page={page}"

            # Add some randomization to avoid detection
            if random.random() < 0.3:  # 30% chance to add ref parameter
                url += f"&ref=sr_pg_{page}"

            response = await self.get_page_async(url)
            if not response:
                print(f"Failed to fetch page {page}")
                continue

            # Save HTML if requested
            if save_html:
                html_filename = os.path.join(
                    self.output_dir, f"page_{page}_{query.replace(' ', '_')}.html"
                )
                with open(html_filename, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved HTML to: {html_filename}")

            soup = BeautifulSoup(response.text, "html.parser")

            # Check if we got blocked or redirected
            if (
                "Robot Check" in response.text
                or "api-services-support@amazon.com" in response.text
            ):
                print("Detected Amazon bot detection page!")
                break

            # Extract product blocks
            blocks = self.extract_product_blocks(soup)

            if not blocks:
                print(f"No product blocks found on page {page}")
                # Try to save the page for debugging
                debug_filename = os.path.join(
                    self.output_dir, f"debug_page_{page}.html"
                )
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved debug HTML to: {debug_filename}")
                continue

            print(f"Found {len(blocks)} product blocks on page {page}")
            all_blocks.extend(blocks)

            # Add delay between pages
            if page < pages:
                delay = random.uniform(3, 8)
                print(f"Waiting {delay:.2f} seconds before next page...")
                await asyncio.sleep(delay)  # Use asyncio.sleep

        print(f"\nTotal product blocks collected: {len(all_blocks)}")
        return all_blocks

    def extract_title(self, product_block):
        """Extract product title with multiple fallback methods"""
        try:
            # Method 1: aria-label in h2 (most reliable)
            title_element = product_block.find("h2", {"aria-label": True})
            if title_element and title_element.get("aria-label", "").strip():
                return title_element.get("aria-label", "").strip()

            # Method 2: span inside h2
            title_span = product_block.select_one("h2 span")
            if title_span and title_span.get_text(strip=True):
                return title_span.get_text(strip=True)

            # Method 3: direct h2 text
            h2_element = product_block.find("h2")
            if h2_element and h2_element.get_text(strip=True):
                return h2_element.get_text(strip=True)

            # Method 4: image alt text (last resort)
            img_element = product_block.select_one("img.s-image")
            if img_element and img_element.get("alt"):
                alt_text = img_element.get("alt")
                return alt_text.split("...")[0] if "..." in alt_text else alt_text

            return None
        except Exception as e:
            print(f"Title extraction error: {e}")
            return None

    def extract_prices(self, product_block):
        """Extracts current and original prices from an Amazon product block"""
        prices = {"current": None, "original": None}

        try:
            # CURRENT PRICE - More reliable extraction
            price_span = product_block.select_one(".a-price .a-offscreen")
            if price_span:
                current_price_str = price_span.get_text(strip=True)
                prices["current"] = float(
                    current_price_str.replace("$", "").replace(",", "")
                )
            else:
                # Fallback to whole+fraction parts if a-offscreen not found
                price_whole = product_block.select_one(".a-price .a-price-whole")
                price_fraction = product_block.select_one(".a-price .a-price-fraction")
                if price_whole and price_fraction:
                    # PROPERLY handle the decimal point
                    whole_part = (
                        price_whole.get_text(strip=True)
                        .replace(",", "")
                        .replace(".", "")
                    )
                    fraction_part = price_fraction.get_text(strip=True)
                    current_price_str = f"{whole_part}.{fraction_part}"
                    prices["current"] = float(current_price_str)

            # ORIGINAL PRICE
            original_price = product_block.select_one(".a-text-price .a-offscreen")
            if original_price:
                original_price_str = original_price.get_text(strip=True)
                prices["original"] = float(
                    original_price_str.replace("$", "").replace(",", "")
                )
            else:
                # Alternative original price location
                list_price = product_block.find(
                    "span", string=re.compile(r"List:\s*\$")
                )
                if list_price:
                    next_span = list_price.find_next("span", class_="a-offscreen")
                    if next_span:
                        original_price_str = next_span.get_text(strip=True)
                        prices["original"] = float(
                            original_price_str.replace("$", "").replace(",", "")
                        )

        except Exception as e:
            print(f"Price extraction error: {str(e)}")

        return prices

    def extract_rating(self, product_block):
        """Extract product rating with more comprehensive selectors"""
        try:
            # Try multiple rating element patterns
            rating_selectors = [
                "i.a-icon-star-small span.a-icon-alt",  # Standard rating
                'span[aria-label*="out of 5 stars"]',  # Aria-label rating
                "i.a-icon-star span.a-icon-alt",  # Alternate star icon
                "span.a-icon-alt",  # Any rating text
                "div.a-row span.a-size-base",  # Sometimes in a row
                "div.averageCustomerReviews span.a-icon-alt",  # Alternate location
            ]

            for selector in rating_selectors:
                rating_element = product_block.select_one(selector)
                if rating_element:
                    rating_text = (
                        rating_element.get_text(strip=True)
                        if rating_element.get_text(strip=True)
                        else rating_element.get("aria-label", "")
                    )
                    if rating_text:
                        # Extract numeric rating (4.3 out of 5 → 4.3)
                        rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                        if rating_match:
                            return rating_match.group(1)

            # Fallback to review count element which sometimes contains rating
            reviews_element = product_block.select_one(
                "span.a-size-base.s-underline-text"
            )
            if reviews_element and "out of 5" in reviews_element.get_text():
                rating_match = re.search(r"(\d+\.?\d*)", reviews_element.get_text())
                if rating_match:
                    return rating_match.group(1)

            return None
        except Exception as e:
            print(f"Rating extraction error: {e}")
            return None

    def extract_reviews(self, product_block):
        """Extract review count"""
        try:
            reviews_element = product_block.select_one(
                "span.a-size-base.s-underline-text"
            )
            if reviews_element and reviews_element.get_text(strip=True):
                review_text = reviews_element.get_text(strip=True)
                review_match = re.search(r"(\d+(?:,\d+)*)", review_text)
                if review_match:
                    return review_match.group(1)

            review_patterns = [
                r"(\d+(?:,\d+)*)\s*(?:ratings?|reviews?)",
                r"\((\d+(?:,\d+)*)\)",
                r"(\d+(?:,\d+)*)\s*customer",
            ]

            text_content = product_block.get_text()
            for pattern in review_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    return match.group(1)

            return None
        except Exception as e:
            print(f"Reviews extraction error: {e}")
            return None

    def extract_delivery(self, product_block):
        """Extract delivery information"""
        try:
            delivery_element = product_block.select_one(
                "div.udm-primary-delivery-message"
            )
            if delivery_element:
                delivery_text = " ".join(delivery_element.stripped_strings)
                if delivery_text.strip():
                    return delivery_text.strip()

            delivery_secondary = product_block.select_one(
                "div.udm-secondary-delivery-message"
            )
            if delivery_secondary:
                delivery_text = " ".join(delivery_secondary.stripped_strings)
                if delivery_text.strip():
                    return delivery_text.strip()

            return None
        except Exception as e:
            print(f"Delivery extraction error: {e}")
            return None

    def extract_product_url(self, product_block):
        """Construct product URL using ASIN"""
        try:
            asin = product_block.get("data-asin")
            if asin and asin.strip():
                return f"https://www.amazon.com/dp/{asin.strip()}"
            return None
        except Exception as e:
            print(f"URL construction error: {e}")
            return None

    def extract_amazon_product_info(self, product_block):
        """Extract all product information from a product block"""
        if not product_block:
            return None

        prices = self.extract_prices(product_block)
        asin = product_block.get("data-asin")

        product_info = {
            "asin": asin,
            "title": self.extract_title(product_block),
            "current_price": prices["current"],
            "original_price": prices["original"],
            "rating": self.extract_rating(product_block),
            "reviews": self.extract_reviews(product_block),
            "delivery": self.extract_delivery(product_block),
            "product_url": self.extract_product_url(product_block),
            "scraped_at": datetime.now().isoformat(),
        }

        # Filter out None values
        return {k: v for k, v in product_info.items() if v is not None}

    async def scrape_search_async(
        self, query, pages=1, save_html=False, save_blocks=False
    ):
        """Main async method to scrape Amazon search results"""
        print(f"Starting Amazon scrape for query: '{query}'")

        # Get product blocks from search pages
        product_blocks = await self.get_search_results_async(query, pages, save_html)

        if not product_blocks:
            print("No product blocks found!")
            return []

        # Save raw blocks if requested
        if save_blocks:
            blocks_filename = os.path.join(
                self.output_dir, f"blocks_{query.replace(' ', '_')}.html"
            )
            with open(blocks_filename, "w", encoding="utf-8") as f:
                for i, block in enumerate(product_blocks):
                    f.write(f"<!-- BLOCK {i+1} -->\n")
                    f.write(str(block))
                    f.write(f"\n<!-- END BLOCK {i+1} -->\n\n")
            print(f"Saved product blocks to: {blocks_filename}")

        # Extract product information
        products = []
        print(f"\nExtracting product information from {len(product_blocks)} blocks...")

        for i, block in enumerate(product_blocks, 1):
            try:
                product_info = self.extract_amazon_product_info(block)
                if product_info and product_info.get("title"):
                    products.append(product_info)
                    print(
                        f"✓ Block {i}: Extracted - {product_info.get('title', 'No title')[:60]}..."
                    )
                else:
                    print(f"✗ Block {i}: Failed to extract meaningful data")
            except Exception as e:
                print(f"✗ Block {i}: Error during extraction - {e}")

        # Save results if main
        if __name__ == "__main__":
            if products:
                results_filename = os.path.join(
                    self.output_dir,
                    f"products_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                )
                with open(results_filename, "w", encoding="utf-8") as f:
                    json.dump(products, f, indent=4, ensure_ascii=False)
                print(f"\n✅ Saved {len(products)} products to: {results_filename}")

        return products

    # Convenience method to run async scraping
    def scrape_search(self, query, pages=1, save_html=False, save_blocks=False):
        """Convenience method to run async scraping"""
        return asyncio.run(
            self.scrape_search_async(query, pages, save_html, save_blocks)
        )


# Example usage
async def main():
    scraper = AmazonScraper()

    query = "laptop"
    pages = 5  # Start with fewer pages for testing

    products = await scraper.scrape_search_async(
        query=query,
        pages=pages,
        save_html=True,  # Save raw HTML for debugging
        save_blocks=True,  # Save extracted blocks for debugging
    )

    print(f"\n=== SCRAPING COMPLETE ===")
    print(f"Query: {query}")
    print(f"Pages: {pages}")
    print(f"Products found: {len(products)}")

    # Print first few products as example
    for i, product in enumerate(products[:3], 1):
        print(f"\n--- Product {i} ---")
        for key, value in product.items():
            print(f"{key}: {value}")


# Run the async version
if __name__ == "__main__":
    # For environments that already have an event loop (like Jupyter)
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a task
            import nest_asyncio

            nest_asyncio.apply()
            asyncio.run(main())
        else:
            asyncio.run(main())
    except RuntimeError:
        # No event loop, safe to use asyncio.run
        asyncio.run(main())
    except ImportError:
        # nest_asyncio not available, try alternative approach
        print("For Jupyter notebooks, install nest_asyncio: pip install nest_asyncio")
        asyncio.run(main())
