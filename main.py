# main.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import Base, Product  # import your Base and models
from scraper import AmazonScraper
from pprint import pprint


def setup_database():
    # Create an SQLite database file called 'products.db' (or use :memory: for in-memory)
    engine = create_engine("sqlite:///products.db", echo=True)

    # Create all tables defined in Base subclasses
    Base.metadata.create_all(engine)

    return engine


scraper = AmazonScraper()

if __name__ == "__main__":
    engine = setup_database()

    # Optional: Open a session and add example data
    # with Session(engine) as session:
    #     # Example: Add a new product
    #     new_product = Product(
    #         title="Example Product",
    #         current_price=99.99,
    #         original_price=149.99,
    #         rating="4.5",
    #         reviews="123",
    #         delivery="Free delivery in 3 days",
    #         product_url="https://amazon.com/dp/example123",
    #     )
    #     session.add(new_product)
    #     session.commit()

    print("Database setup complete and example product added.")
    pprint(scraper.scrape_search("laptop", 5))
