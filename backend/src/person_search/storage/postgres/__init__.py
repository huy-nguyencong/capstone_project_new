"""PostgreSQL persistence adapter namespace."""

from person_search.storage.postgres.client import PostgresStorage
from person_search.storage.postgres.models import Area, Base, Camera, User

__all__ = ["Area", "Base", "Camera", "PostgresStorage", "User"]
