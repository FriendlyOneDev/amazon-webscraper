import argparse
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, select, func, cast, Float
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import uvicorn

from models import Base, Product
from scraper import AmazonScraper

# ---------- Configuration ----------

templates = Jinja2Templates(directory="static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    engine = create_db_engine("amazon.db")
    app.state.engine = engine
    yield
    # Shutdown (optional cleanup logic here)
    engine.dispose()


app = FastAPI(lifespan=lifespan)


# ---------- Database Setup ----------


def create_db_engine(db_path: str = "amazon.db"):
    engine = create_engine(f"sqlite:///{db_path}", echo=True)
    Base.metadata.create_all(engine)
    return engine


# ---------- Scraper Logic ----------


class DatabaseManager:
    def __init__(self, engine):
        self.engine = engine

    def save_products(self, products: List[Dict]) -> int:
        saved_count = 0
        with Session(self.engine) as session:
            for product_data in products:
                try:
                    existing = (
                        session.query(Product)
                        .filter_by(product_url=product_data["product_url"])
                        .first()
                    )

                    if existing:
                        existing.current_price = product_data.get("current_price")
                        existing.original_price = product_data.get("original_price")
                        existing.rating = product_data.get("rating")
                        existing.reviews = product_data.get("reviews")
                        existing.delivery = product_data.get("delivery")
                        existing.seller = product_data.get("seller")
                        existing.scraped_at = datetime.utcnow()
                    else:
                        new_product = Product(
                            title=product_data["title"],
                            current_price=product_data.get("current_price"),
                            original_price=product_data.get("original_price"),
                            rating=product_data.get("rating"),
                            reviews=product_data.get("reviews"),
                            delivery=product_data.get("delivery"),
                            seller=product_data.get("seller"),
                            product_url=product_data["product_url"],
                        )
                        session.add(new_product)

                    saved_count += 1
                except Exception as e:
                    print(
                        f"Error processing product {product_data.get('product_url')}: {e}"
                    )
                    session.rollback()

            session.commit()
        return saved_count


# ---------- Web Server Endpoints ----------


@app.get("/", response_class=HTMLResponse)
def read_products(
    request: Request,
    min_rating: Optional[str] = Query(None),
    max_price: Optional[str] = Query(None),
    min_reviews: Optional[str] = Query(None),
):
    with Session(app.state.engine) as session:
        stmt = select(Product).where(Product.current_price != None)

        try:
            if min_rating not in (None, ""):
                stmt = stmt.where(cast(Product.rating, Float) >= float(min_rating))
            if max_price not in (None, ""):
                stmt = stmt.where(Product.current_price <= float(max_price))
            if min_reviews not in (None, ""):
                stmt = stmt.where(cast(Product.reviews, Float) >= int(min_reviews))
        except ValueError:
            pass

        products = session.scalars(stmt).all()

    return templates.TemplateResponse(
        "products.html", {"request": request, "products": products}
    )


@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    with Session(app.state.engine) as session:
        avg_price_stmt = select(func.avg(Product.current_price)).where(
            cast(Product.rating, Float) >= 4.0, Product.current_price != None
        )
        avg_price = session.scalar(avg_price_stmt)

        discount_stmt = (
            select(Product)
            .where(Product.original_price != None, Product.current_price != None)
            .order_by((Product.original_price - Product.current_price).desc())
        )
        top_discount = session.scalars(discount_stmt).first()

        value_stmt = (
            select(Product)
            .where(Product.current_price != None, cast(Product.rating, Float) != None)
            .order_by((cast(Product.rating, Float) / Product.current_price).desc())
            .limit(3)
        )
        top_value = session.scalars(value_stmt).all()

        price_dist_stmt = select(Product.current_price).where(
            Product.current_price != None
        )
        prices = [p[0] for p in session.execute(price_dist_stmt).all()]

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "avg_price": round(avg_price, 2) if avg_price else None,
            "top_discount": top_discount,
            "top_value": top_value,
            "prices": prices,
        },
    )


# ---------- CLI ----------


def parse_arguments():
    parser = argparse.ArgumentParser(description="Amazon Scraper & Server")
    parser.add_argument(
        "--mode",
        choices=["scrape", "serve"],
        required=True,
        help="Mode to run: scrape or serve",
    )
    parser.add_argument("--query", type=str, default="laptop", help="Search query")
    parser.add_argument("--pages", type=int, default=5, help="Pages to scrape")
    parser.add_argument("--db", type=str, default="amazon.db", help="Database path")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    return parser.parse_args()


# ---------- Entrypoint ----------

if __name__ == "__main__":
    args = parse_arguments()
    engine = create_db_engine(args.db)
    app.state.engine = engine

    if args.mode == "scrape":
        print(f"Scraping '{args.query}' ({args.pages} pages)...")
        scraper = AmazonScraper(output_dir="debug_output" if args.debug else None)
        products = scraper.scrape_search(
            query=args.query,
            pages=args.pages,
            save_html=args.debug,
            save_blocks=args.debug,
        )
        if products:
            db_manager = DatabaseManager(engine)
            saved = db_manager.save_products(products)
            print(f"Processed {saved}/{len(products)} products.")
        else:
            print("No products found.")
    elif args.mode == "serve":
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
