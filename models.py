from typing import Optional
from sqlalchemy import ForeignKey, Float, Integer, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "product"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512))
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    original_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rating: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reviews: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    delivery: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    product_url: Mapped[str] = mapped_column(String(2048), unique=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"Product(title={self.title!r}, current_price={self.current_price}, "
            f"original_price={self.original_price}, rating={self.rating!r}, "
            f"reviews={self.reviews!r}, delivery={self.delivery!r}, "
            f"product_url={self.product_url!r})"
        )
