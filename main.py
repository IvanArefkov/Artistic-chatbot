from typing import Annotated
from fastapi import FastAPI, UploadFile, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from db.models.base import Base
import os
import dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from utils.util import scape_format_embed, retrieve, scrape_links
dotenv.load_dotenv()


app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

origins = [
    "http://localhost:3000",
]
variable_origin = os.getenv("ORIGIN")
if variable_origin:
    origins.append(str(variable_origin))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = create_engine("postgresql://chatbot_user:chatbot_pass@localhost:5432/chatbot_db", echo=True)

class UserQuery(BaseModel):
    message: str



@app.get("/")
async def root():
    return {"message": "hello world"}


@app.get("/db_init")
async def db_init(token: Annotated[str,Depends(oauth2_scheme)]):
    Base.metadata.create_all(engine)
    return {"status":"success init db"}

@app.post("/chat")
async def rag_search(query: UserQuery):
    docs_content = retrieve(query.message)
    message = [
        SystemMessage(content=f'You are a helpful assistant. Provide a maximum 1 paragraph answer, no more then 300 characters. At the end of the response always ask the user a followup question. Respond only in Russian language.  Answer the users message based on this context: {docs_content}'),
        HumanMessage(content=query.message)
    ]
    model = init_chat_model("gpt-5-mini", model_provider="openai")
    response = model.invoke(message)
    return response.text()

@app.post("/upload-site-map")
async def upload_file(file: UploadFile, token: Annotated[str,Depends(oauth2_scheme)]):
    file_read = await file.read()
    text_file = file_read.decode("utf-8")
    site_map = text_file.split("\n")
    for site in site_map:
        scape_format_embed(site)
    return {
        'response':'upload success',
    }


@app.post("/scrape")
async def test_model(link: str, token: Annotated[str, Depends(oauth2_scheme)]):
    product_name = scape_format_embed(link)
    return {'message': product_name}

@app.post('/find-links')
def find_links(link: str, token: Annotated[str, Depends(oauth2_scheme)]):
    scrape_links(link)
    return {'message': 'link found'}

@app.post("/token")
async def authorise(form_data: Annotated[OAuth2PasswordRequestForm,Depends()]):
    user = form_data.username
    password = form_data.password
    if user != os.getenv("ADMIN") or password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": user, 'token_type': 'bearer'}
