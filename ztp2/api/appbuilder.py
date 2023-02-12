from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.entries import entries_router
from .routers.models import models_router


def get_app(docs_url: str = '/docs', redoc_url: str = '/redoc') -> FastAPI:
    app = FastAPI(docs_url=docs_url, redoc_url=redoc_url)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(entries_router, prefix='/entries', tags=['Entries'])
    app.include_router(models_router, prefix='/models', tags=['Models'])
    return app
