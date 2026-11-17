"""FastAPI application entry point for ResolveX USM Platform."""
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import (
    agent,
    knowledge,
    auth,
    stats,
    incidents,
    approvals,
    service_requests,
    assets,
    sla,
    mcp_monitor,
    employee,
    workforce,
)
from backend.database import SessionLocal
from backend.services.workforce import seed_workforce


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth.seed_demo_users()
    db = SessionLocal()
    try:
        seed_workforce(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="ResolveX USM Platform API",
    description="Unified Service Management (USM) Autonomous IT Incident & Service Request Resolution Platform",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers under /api
app.include_router(auth.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(approvals.router, prefix="/api")
app.include_router(service_requests.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(sla.router, prefix="/api")
app.include_router(mcp_monitor.router, prefix="/api")
app.include_router(employee.router, prefix="/api")
app.include_router(employee.admin_router, prefix="/api")
app.include_router(workforce.router, prefix="/api")
app.include_router(knowledge.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "resolvex-backend"}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
