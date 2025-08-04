import requests
import time
import random
import argparse
import os
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup


class AmazonScraper:
    def __init__(self):
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
        self.output_dir = None

    def get_page(self, url, attempt=1, max_attempts=3):
        """Fetch a page with retry logic"""
        try:
            self.headers["User-Agent"] = random.choice(self.user_agents)
            delay = random.uniform(2, 5) * attempt
            print(f"Attempt {attempt}: Waiting {delay:.2f} seconds...")
            time.sleep(delay)

            print(f"Fetching URL: {url}")
            response = self.session.get(url, headers=self.headers)

            if response.status_code != 200:
                print(f"Status {response.status_code}, retrying...")
                if attempt < max_attempts:
                    return self.get_page(url, attempt + 1, max_attempts)
                return None

            if "captcha" in response.text.lower():
                print("CAPTCHA detected!")
                return None

            return response

        except Exception as e:
            print(f"Error fetching page: {e}")
            if attempt < max_attempts:
                return self.get_page(url, attempt + 1, max_attempts)
            return None

    def get_search_results(self, query, pages=1):
        """Scrape multiple pages and return product block elements"""
        results = []

        for page in range(1, pages + 1):
            url = f"https://www.amazon.com/s?k={query}&page={page}"
            response = self.get_page(url)
            if not response:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            blocks = soup.find_all("div", {"data-component-type": "s-search-result"})
            results.extend(blocks)

        return results

    def extract_title(self, product_block):
        """Extract product title from Amazon product block"""
        try:
            # Look for the h2 element with aria-label or the span inside it
            title_element = product_block.find("h2", {"aria-label": True})
            if title_element:
                return title_element.get("aria-label").strip()

            # Alternative: look for span inside h2
            h2_element = product_block.find("h2")
            if h2_element:
                title_span = h2_element.find("span")
                if title_span:
                    return title_span.get_text(strip=True)

            return None
        except:
            return None

    def extract_current_price(self, product_block):
        """Extract current price from Amazon product block"""
        try:
            # Look for price in various span classes
            price_classes = ["a-color-base", "a-price-whole", "a-offscreen"]
            for class_name in price_classes:
                price_elements = product_block.find_all("span", class_=class_name)
                for element in price_elements:
                    text = element.get_text(strip=True)
                    if "$" in text and re.match(r"\$[\d,]+\.?\d*", text):
                        return text

            # Look for price in a-price containers
            price_containers = product_block.find_all("span", class_="a-price")
            for container in price_containers:
                price_text = container.get_text(strip=True)
                price_match = re.search(r"\$[\d,]+\.?\d{0,2}", price_text)
                if price_match:
                    return price_match.group()

            # Search all text for price pattern as last resort
            all_text = product_block.get_text()
            price_matches = re.findall(r"\$[\d,]+\.?\d{0,2}", all_text)
            if price_matches:
                # Return the first valid price found
                for price in price_matches:
                    # Filter out obviously wrong prices (like $0.00, $1.00 etc.)
                    price_num = float(price.replace("$", "").replace(",", ""))
                    if price_num > 10:  # Reasonable minimum price filter
                        return price

            return None
        except:
            return None

    def extract_original_price(self, product_block):
        """Extract original price (if discounted) from Amazon product block"""
        try:
            # Look for strikethrough price or list price
            strikethrough = product_block.find("span", class_="a-price-range")
            if strikethrough:
                return strikethrough.get_text(strip=True)

            # Look for text-decoration: line-through in style
            for element in product_block.find_all(["span", "div"]):
                style = element.get("style", "")
                if "line-through" in style:
                    text = element.get_text(strip=True)
                    if "$" in text:
                        return text

            # If no original price found, it's likely not discounted
            return None
        except:
            return None

    def extract_rating(self, product_block):
        """Extract product rating from Amazon product block"""
        try:
            # Look for aria-label with rating info
            rating_element = product_block.find(
                "a", {"aria-label": re.compile(r"[\d\.]+\s+out\s+of\s+5\s+stars")}
            )
            if rating_element:
                aria_label = rating_element.get("aria-label")
                rating_match = re.search(
                    r"([\d\.]+)\s+out\s+of\s+5\s+stars", aria_label
                )
                if rating_match:
                    return float(rating_match.group(1))

            # Alternative: look for span with rating text
            rating_span = product_block.find("span", class_="a-icon-alt")
            if rating_span:
                text = rating_span.get_text(strip=True)
                rating_match = re.search(r"([\d\.]+)\s+out\s+of\s+5", text)
                if rating_match:
                    return float(rating_match.group(1))

            # Look for rating in any span or div text
            for element in product_block.find_all(["span", "div", "a"]):
                text = element.get_text(strip=True)
                if re.search(r"[\d\.]+\s+out\s+of\s+5", text):
                    rating_match = re.search(r"([\d\.]+)\s+out\s+of\s+5", text)
                    if rating_match:
                        return float(rating_match.group(1))

            return None
        except:
            return None

    def extract_reviews_count(self, product_block):
        """Extract number of reviews from Amazon product block"""
        try:
            # Look for aria-label with ratings count
            reviews_element = product_block.find(
                "a", {"aria-label": re.compile(r"\d+\s+ratings?")}
            )
            if reviews_element:
                aria_label = reviews_element.get("aria-label")
                reviews_match = re.search(r"(\d+)", aria_label)
                if reviews_match:
                    return int(reviews_match.group(1))

            # Look for text with "ratings" or "reviews"
            for element in product_block.find_all(["span", "a", "div"]):
                text = element.get_text(strip=True)
                # Match patterns like "1,234 ratings", "567 reviews", "(123)"
                if re.search(r"\d+.*?(?:rating|review)", text, re.IGNORECASE):
                    numbers = re.findall(r"(\d+(?:,\d+)*)", text)
                    if numbers:
                        return int(numbers[0].replace(",", ""))

                # Look for parenthetical numbers that might be review counts
                paren_match = re.search(r"\((\d+(?:,\d+)*)\)", text)
                if paren_match:
                    return int(paren_match.group(1).replace(",", ""))

            # Alternative: look for span with number followed by ratings text
            for element in product_block.find_all("span"):
                text = element.get_text(strip=True)
                if re.match(r"^\d+$", text):
                    # Check if next sibling or parent contains "ratings"
                    parent_text = element.parent.get_text() if element.parent else ""
                    if "rating" in parent_text.lower():
                        return int(text)

            return None
        except:
            return None

    def extract_delivery_availability(self, product_block):
        """Extract delivery availability from Amazon product block"""
        try:
            # Look for delivery-related text
            delivery_keywords = [
                "delivery",
                "shipping",
                "arrives",
                "get it by",
                "prime",
            ]

            for element in product_block.find_all(["span", "div"]):
                text = element.get_text(strip=True).lower()
                for keyword in delivery_keywords:
                    if keyword in text:
                        return element.get_text(strip=True)

            # Check for Prime availability
            prime_element = product_block.find("i", class_="a-icon-prime")
            if prime_element:
                return "Prime eligible"

            # Check for "No featured offers available" or similar
            no_offers = product_block.find(
                string=re.compile(r"No featured offers available")
            )
            if no_offers:
                return "No featured offers available"

            return "Standard delivery"
        except:
            return None

    def extract_seller(self, product_block):
        """Extract seller information from Amazon product block"""
        try:
            # Look for "by" followed by seller name
            by_text = product_block.find(string=re.compile(r"by\s+"))
            if by_text:
                seller_match = re.search(r"by\s+(.+)", by_text.strip())
                if seller_match:
                    return seller_match.group(1).strip()

            # Look for seller information in various span classes
            seller_classes = ["a-size-base", "s-link-style"]
            for class_name in seller_classes:
                elements = product_block.find_all("span", class_=class_name)
                for element in elements:
                    text = element.get_text(strip=True)
                    if "sold by" in text.lower() or "ships from" in text.lower():
                        return text

            # Default to Amazon if no specific seller found
            return "Amazon"
        except:
            return "Amazon"

    def extract_product_url(self, product_block):
        """Extract product URL from Amazon product block"""
        try:
            # Look for main product link (usually in title or image)
            title_link = product_block.find("a", class_="a-link-normal s-line-clamp-2")
            if title_link and title_link.get("href"):
                href = title_link.get("href")
                # Convert relative URL to absolute
                if href.startswith("/"):
                    return f"https://amazon.com{href}"
                return href

            # Look for sponsored product links (s-faceout-link class)
            sponsored_link = product_block.find(
                "a", class_="a-link-normal s-faceout-link"
            )
            if sponsored_link and sponsored_link.get("href"):
                href = sponsored_link.get("href")
                # Convert relative URL to absolute
                if href.startswith("/"):
                    return f"https://amazon.com{href}"
                return href

            # Alternative: look for any link with /dp/ in href (regular products)
            for link in product_block.find_all("a", href=True):
                href = link.get("href")
                if "/dp/" in href:
                    if href.startswith("/"):
                        return f"https://amazon.com{href}"
                    return href

            # Last resort: look for any link with /sspa/click (sponsored products)
            for link in product_block.find_all("a", href=True):
                href = link.get("href")
                if "/sspa/click" in href:
                    if href.startswith("/"):
                        return f"https://amazon.com{href}"
                    return href

            return None
        except:
            return None

    def extract_product_data(self, product_block):
        """Extract all product data from a single Amazon product block"""
        return {
            "title": self.extract_title(product_block),
            "current_price": self.extract_current_price(product_block),
            "original_price": self.extract_original_price(product_block),
            "rating": self.extract_rating(product_block),
            "reviews_count": self.extract_reviews_count(product_block),
            "delivery_availability": self.extract_delivery_availability(product_block),
            "seller": self.extract_seller(product_block),
            "product_url": self.extract_product_url(product_block),
            "is_sponsored": self.is_sponsored_product(product_block),
            "scraped_at": datetime.now().isoformat(),
        }

    def is_sponsored_product(self, product_block):
        """Check if a product block is a sponsored product"""
        try:
            # Look for "Sponsored" text in various elements
            sponsored_indicators = [
                product_block.find(
                    "span", {"aria-label": re.compile(r".*[Ss]ponsored.*")}
                ),
                product_block.find("span", string=re.compile(r"[Ss]ponsored")),
                product_block.find(string=re.compile(r"[Ss]ponsored")),
            ]

            # Check if any sponsored indicator was found
            for indicator in sponsored_indicators:
                if indicator:
                    return True

            # Also check for sponsored class names or data attributes
            if product_block.find(
                attrs={"class": re.compile(r".*sponsored.*", re.IGNORECASE)}
            ):
                return True

            return False
        except:
            return False

    def check_missing_data(self, product_data, product_block):
        """Check if product is missing any required data (except original_price) and print block if so"""
        # Only show debug output if run as main script
        if __name__ != "__main__":
            return False

        required_fields = [
            "title",
            "current_price",
            "rating",
            "reviews_count",
            "delivery_availability",
            "seller",
            "product_url",
        ]
        missing_fields = []

        for field in required_fields:
            if product_data.get(field) is None:
                missing_fields.append(field)

        if missing_fields:
            print(f"\nProduct missing data: {', '.join(missing_fields)}")
            print(f"   Title: {product_data.get('title', 'N/A')}")
            print("=" * 80)
            print(product_block.prettify())
            print("=" * 80)
            return True
        return False

    def save_to_json(self, products_data, json_file):
        """Save product data to JSON file"""
        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(products_data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(products_data)} products to JSON file: {json_file}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")

    def process_and_save_products(self, query, pages=1, json_file="amazon.json"):
        """
        Scrape Amazon search results, extract product data, and save to JSON

        Args:
            query (str): Search query
            pages (int): Number of pages to scrape
            json_file (str): JSON output file path

        Returns:
            list: List of extracted product data dictionaries
        """
        print(f"Scraping Amazon for query: '{query}' ({pages} pages)")
        print("Including sponsored products in results")

        # Get product blocks from search results
        product_blocks = self.get_search_results(query, pages)

        if not product_blocks:
            print("No product blocks found!")
            return []

        print(f"Found {len(product_blocks)} product blocks. Extracting data...")

        # Extract data from each product block
        products_data = []
        sponsored_count = 0
        for i, block in enumerate(product_blocks, 1):
            print(f"Processing product {i}/{len(product_blocks)}")

            # Check if product is sponsored (but always include it)
            is_sponsored = self.is_sponsored_product(block)
            if is_sponsored:
                sponsored_count += 1
                print(f"  - Including sponsored product {i}")

            product_data = self.extract_product_data(block)

            # Check for missing data and print block if needed (only when run as main)
            self.check_missing_data(product_data, block)

            # Only add products that have at least a title
            if product_data.get("title"):
                products_data.append(product_data)
            else:
                print(f"  - Skipping product {i} (no title found)")

        print(f"Found {sponsored_count} sponsored products (all included)")

        # Save to JSON
        if products_data:
            self.save_to_json(products_data, json_file)
        else:
            print("No valid products found to save!")

        return products_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Product Scraper")
    parser.add_argument(
        "--query", type=str, default="laptop", help="Search query (default: laptop)"
    )
    parser.add_argument(
        "--pages", type=int, default=5, help="Number of pages to scrape (default: 5)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="amazon.json",
        help="JSON output file (default: amazon.json)",
    )

    args = parser.parse_args()

    print(f"Starting Amazon Scraper with:")
    print(f"Query: {args.query}")
    print(f"Pages: {args.pages}")
    print(f"Output: {args.output}")

    scraper = AmazonScraper()
    products = scraper.process_and_save_products(args.query, args.pages, args.output)

    print(
        f"\nScraping completed! Found {len(products)} products saved to {args.output}"
    )
