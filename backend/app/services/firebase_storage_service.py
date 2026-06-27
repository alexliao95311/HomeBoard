"""Firebase Cloud Storage client initialization.

The client is initialized lazily so API development does not require Firebase
credentials until a storage operation is performed.
"""

from functools import lru_cache

from firebase_admin import storage
from google.cloud.storage.bucket import Bucket

from app.services.firebase_app import get_firebase_app


@lru_cache(maxsize=1)
def get_storage_bucket() -> Bucket:
    """Return the authenticated Firebase Storage bucket."""
    return storage.bucket(app=get_firebase_app())
