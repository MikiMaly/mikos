from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def get_or_create_user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
        db.flush()
    return user
