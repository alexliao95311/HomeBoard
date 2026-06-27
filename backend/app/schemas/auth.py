from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    uid: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    email_verified: bool = False
