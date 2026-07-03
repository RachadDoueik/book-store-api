"""Initial tables for bookshop domain."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("bio", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_authors_id", "authors", ["id"])
    op.create_index("ix_authors_name", "authors", ["name"])

    op.create_table(
        "books",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("isbn", sa.String(length=32), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=False, default=0),
        sa.Column("page_count" , sa.Integer() , nullable=False , default = 0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("isbn", name="uq_books_isbn"),
    )
    op.create_index("ix_books_id", "books", ["id"])
    op.create_index("ix_books_title", "books", ["title"])
    op.create_index("ix_books_isbn", "books", ["isbn"])

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "carts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_carts_user_id"),
    )
    op.create_index("ix_carts_id", "carts", ["id"])

    op.create_table(
        "wishlists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_wishlists_user_id"),
    )
    op.create_index("ix_wishlists_id", "wishlists", ["id"])

    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, default="pending"),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_orders_id", "orders", ["id"])
    op.create_index("ix_orders_user_id", "orders", ["user_id"])

    op.create_table(
        "book_authors",
        sa.Column("book_id", UUID(as_uuid=True), sa.ForeignKey("books.id"), primary_key=True),
        sa.Column(
            "author_id",
            UUID(as_uuid=True),
            sa.ForeignKey("authors.id"),
            primary_key=True,
        ),
    )

    op.create_table(
        "cart_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("cart_id", UUID(as_uuid=True), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column("book_id", UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, default=1),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "cart_id",
            "book_id",
            name="uq_cart_items_cart_id_book_id",
        ),
    )
    op.create_index("ix_cart_items_id", "cart_items", ["id"])

    op.create_table(
        "wishlist_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "wishlist_id",
            UUID(as_uuid=True),
            sa.ForeignKey("wishlists.id"),
            nullable=False,
        ),
        sa.Column("book_id", UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "wishlist_id",
            "book_id",
            name="uq_wishlist_items_wishlist_id_book_id",
        ),
    )
    op.create_index("ix_wishlist_items_id", "wishlist_items", ["id"])

    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("book_id", UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, default=1),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_order_items_id", "order_items", ["id"])


def downgrade() -> None:
    op.drop_index("ix_order_items_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_wishlist_items_id", table_name="wishlist_items")
    op.drop_table("wishlist_items")

    op.drop_index("ix_cart_items_id", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_table("book_authors")

    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_orders_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_wishlists_id", table_name="wishlists")
    op.drop_table("wishlists")

    op.drop_index("ix_carts_id", table_name="carts")
    op.drop_table("carts")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_books_isbn", table_name="books")
    op.drop_index("ix_books_title", table_name="books")
    op.drop_index("ix_books_id", table_name="books")
    op.drop_table("books")

    op.drop_index("ix_authors_name", table_name="authors")
    op.drop_index("ix_authors_id", table_name="authors")
    op.drop_table("authors")
