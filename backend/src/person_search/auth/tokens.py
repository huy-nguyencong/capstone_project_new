from __future__ import annotations

import hashlib
import hmac
import secrets

CSRF_CONTEXT = b"person-search.csrf.v1"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token_for(session_token: str) -> str:
    return hmac.new(session_token.encode(), CSRF_CONTEXT, hashlib.sha256).hexdigest()


def csrf_matches(session_token: str | None, candidate: str | None) -> bool:
    if not session_token or not candidate:
        return False
    return hmac.compare_digest(csrf_token_for(session_token), candidate)
