from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """
    Shared properties for a User
    """

    first_name: str
    last_name: str
    email: EmailStr


class UserCreate(UserBase):
    """
    Schema for creating a new User
    inherits from UserBase, can add extra fields if needed.
    """

    password: str | None = None


class User(UserBase):
    """
    Schema for reading a User (e.g GET requests).
    inculdes DB-generated fields like IDs, timestamps, etc.
    """

    user_id: int
    created_at: datetime
    updated_at: datetime
    role: str

    model_config = ConfigDict(from_attributes=True)


User.model_rebuild()


class UserLLMConfigBase(BaseModel):
    provider: str  #  "anthropic", "mistral"
    model_name: str # "claude-3-5-sonnet-20240620"
    api_key: str  # The user sends the raw key here

class UserLLMConfigCreate(UserLLMConfigBase):
    """
    Schema for creating/updating the config.
    """
    pass

class UserLLMConfigRead(BaseModel):
    """
    Schema for reading the config back to the UI.
    Security Note: We do NOT return the api_key here.
    """
    provider: str
    model_name: str
    
    model_config = ConfigDict(from_attributes=True)