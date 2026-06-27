"""Shared Firebase Admin application initialization."""

from functools import lru_cache

import firebase_admin
from firebase_admin import App

from app.config import settings


@lru_cache(maxsize=1)
def get_firebase_app() -> App:
    """Return the default Firebase Admin app using Google credentials."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        options = {
            "projectId": settings.firebase_project_id,
            "storageBucket": settings.firebase_storage_bucket,
        }
        return firebase_admin.initialize_app(options=options)
