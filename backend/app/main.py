from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    ai,
    audit,
    auth,
    documents,
    entities,
    findings,
    leads,
    notes,
    review,
    schemas,
    search,
    transactions,
    workspaces,
)

app = FastAPI(
    title="Verity Prism IDP Platform",
    description="Intelligent Document Processing Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(entities.router)
app.include_router(findings.router)
app.include_router(transactions.router)
app.include_router(leads.router)
app.include_router(notes.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(ai.router)
app.include_router(schemas.router)
app.include_router(review.router)
app.include_router(audit.router)

@app.get("/health")
def health():
    return {"status": "ok"}
