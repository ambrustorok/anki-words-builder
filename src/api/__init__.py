from fastapi import APIRouter

from . import admin, cards, decks, profile, session

router = APIRouter(prefix="/api")

router.include_router(session.router, tags=["session"])
router.include_router(profile.router, tags=["profile"])
router.include_router(decks.router, tags=["decks"])
router.include_router(cards.router, tags=["cards"])
router.include_router(admin.router, tags=["admin"])
