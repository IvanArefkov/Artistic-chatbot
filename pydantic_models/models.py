from pydantic import BaseModel

class UserQuery(BaseModel):
    history: str
    session_id: str
    message: str

class SystemMessageModel(BaseModel):
    message: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
