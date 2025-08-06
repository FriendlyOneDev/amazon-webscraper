from typing import Optional
from sqlalchemy import Float, Integer, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    original_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rating: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reviews: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    delivery: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    seller: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    product_url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"Product(id={self.id}, title={self.title[:30]}..., "
            f"price={self.current_price}/{self.original_price}, "
            f"rating={self.rating}, seller={self.seller})"
        )
