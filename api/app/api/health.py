from fastapi import APIRouter, Depends

from app.auth.cf_access import require_user

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/whoami")
async def whoami(email: str = Depends(require_user)) -> dict[str, str]:
    return {"email": email}
