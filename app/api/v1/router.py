"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1.routers import auth, authors, books, cart, categories, orders, users, wishlist , chat


# Aggregate v1 routers in a single entry point.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(authors.router)
api_router.include_router(books.router)
api_router.include_router(categories.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(wishlist.router)
api_router.include_router(users.router)
api_router.include_router(chat.router)