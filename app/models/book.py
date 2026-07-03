from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

from .author import book_authors
from .base import BaseModel

if TYPE_CHECKING:
    from .author import Author
    from .cart import CartItem
    from .category import Category
    from .order import OrderItem
    from .wishlist import WishlistItem


class Book(BaseModel):
    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    release_date: Mapped[date | None] = mapped_column(nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    search_vector: Mapped[TSVECTOR | None] = mapped_column(TSVECTOR, nullable=True)
    

    # Authors is many-to-many; dependent items are deleted with the book.
    authors: Mapped[list["Author"]] = relationship(
        "Author",
        secondary=book_authors,
        back_populates="books",
    )
    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="books",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="book",
        cascade="all, delete-orphan",
    )
    wishlist_items: Mapped[list["WishlistItem"]] = relationship(
        "WishlistItem",
        back_populates="book",
        cascade="all, delete-orphan",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="book",
    )
