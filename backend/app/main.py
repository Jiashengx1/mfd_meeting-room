from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers_auth import router as auth_router
from app.routers_bookings import router as bookings_router
from app.routers_rooms import router as rooms_router

settings = get_settings()

app = FastAPI(title="会议室登记系统 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(rooms_router)
app.include_router(bookings_router)
