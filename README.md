# Amazon Product Scraper & Analytics Web App

This project provides a command-line tool and web server for scraping Amazon product data, saving it into a SQLite database, and displaying product listings and analytics through a FastAPI web interface.

---

## Features

- Scrape Amazon search results for a specified query and number of pages.
- Store product details in a SQLite database.
- Serve a web interface to:
  - Browse products with optional filtering by rating, price, and reviews.
  - View analytics such as average price, top discounts, and best value products.
- Use SQLAlchemy ORM for database operations.
- Support HTML templates with Jinja2 for web pages.
- Command-line interface to choose between scraping mode or server mode.
- Debug options to save HTML and scraped blocks during scraping.

---

## Requirements

- Python 3.8+
- Dependencies (install with pip):
  ```bash
  pip install -r requirements.txt
- Playwright for scraping
  ```bash
  playwright install

## Usage
### Command Line

Run with the following arguments:

python main.py --mode <scrape|serve> [options]

Options

    --mode:

        scrape — Scrape Amazon and save product data to database.

        serve — Start FastAPI web server to browse and analyze products.

    --query: Search term for scraping (default: "laptop").

    --pages: Number of pages to scrape (default: 5).

    --db: Path to SQLite database file (default: "amazon.db").

    --debug: Enable debug mode to save HTML and scraped blocks (only in scrape mode). Creates debug_output directory.

### Web Interface

Once the server is running, open your browser to:
- Product List: http://127.0.0.1:8000/
 - Filter products by:
   - Minimum rating
   - Maximum price
   - Minimum number of reviews
- Analytics: http://127.0.0.1:8000/analytics
 - Displays:
   - Average price of highly rated products
   - Product with highest discount
   - Top 3 products by rating-to-price ratio
   - Price distribution data
