from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    token_type: str
    access_token: str


class TokenData(BaseModel):
    email: str | None = None
