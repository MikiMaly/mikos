import time
from typing import Annotated, Any

import httpx
from fastapi import Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

from app.config import settings

_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _get_jwks() -> dict[str, Any]:
    now = time.time()
    if _jwks_cache["keys"] is not None and now - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]

    url = f"https://{settings.cf_access_team_domain}/cdn-cgi/access/certs"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    data = response.json()
    _jwks_cache["keys"] = data
    _jwks_cache["fetched_at"] = now
    return data


async def require_user(
    cf_access_jwt: Annotated[
        str | None, Header(alias="Cf-Access-Jwt-Assertion")
    ] = None,
) -> str:
    if settings.dev_mode:
        return "dev@local"

    if not cf_access_jwt:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing Cf-Access-Jwt-Assertion header"
        )

    if not settings.cf_access_team_domain or not settings.cf_access_aud:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "CF Access not configured (team domain / aud missing)",
        )

    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(cf_access_jwt)
        kid = unverified_header.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown JWT key id")

        claims = jwt.decode(
            cf_access_jwt,
            key,
            algorithms=["RS256"],
            audience=settings.cf_access_aud,
            options={"verify_iss": False},
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid JWT: {exc}") from exc

    email = str(claims.get("email", "")).lower()
    allowed = settings.allowed_emails
    if allowed and email not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email not in allowlist")

    return email
