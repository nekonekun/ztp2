from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.entries import entries_router
from .routers.models import models_router
from .routers.users import users_router
from .routers.celery import celery_router
from .routers.reports import reports_router


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
    app.include_router(users_router, prefix='/users', tags=['Users'])
    app.include_router(celery_router, prefix='/celery', tags=['Celery Tasks'])
    app.include_router(reports_router, prefix='/reports', tags=['Reports'])
    return app
