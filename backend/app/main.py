"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .api import webhooks, cases, analytics, data, payments


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


app = FastAPI(title="RecoverX — AI Revenue Recovery Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(webhooks.router)
app.include_router(cases.router)
app.include_router(analytics.router)
app.include_router(data.router)
app.include_router(payments.router)


@app.get("/health")
def health():
    return {"status": "ok"}
