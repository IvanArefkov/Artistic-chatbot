from typing import Annotated

from fastapi import FastAPI
from pydantic import AfterValidator, BaseModel

app = FastAPI()


class User(BaseModel):
    name: str
    id: int


def validate_name_length(obj: User):
    if len(obj.name) < 4:
        raise ValueError("Name is too short")
    return obj


@app.get("/")
async def root():
    return {"message": "hello world"}


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}


@app.post("/post-test")
async def post_req(user: Annotated[User, AfterValidator(validate_name_length)]):
    return user
