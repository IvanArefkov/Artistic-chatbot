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
from utils.util import scape_format_embed, retrieve, scrape_links, define_message_intent
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
    history: str
    message: str




@app.get("/")
async def root():
    return {"message": "hello world"}


@app.get("/db_init")
async def db_init(token: Annotated[str,Depends(oauth2_scheme)]):
    Base.metadata.create_all(engine)
    return {"status":"success init db"}

@app.post("/chat")
async def chat(query: UserQuery):
    intent = define_message_intent(message=query.message)
    file = open('system_message.txt', 'r')
    system_prompt = file.read()
    file.close()

    if "НЕ_ИСПОЛЬЗОВАТЬ_RAG" in intent:
        print('НЕ_ИСПОЛЬЗОВАТЬ_RAG')
        message = [
            SystemMessage(content=f'{system_prompt}, История переписки: {query.history}'),
            HumanMessage(content=query.message)
        ]
    else :
        print('ИСПОЛЬЗОВАТЬ_RAG')
        docs_content = retrieve(query.message)
        message = [
            SystemMessage(content=f'{system_prompt},контекст: {docs_content} , История переписки: {query.history}'),
            HumanMessage(content=query.message)
        ]

    model = init_chat_model("gpt-5", model_provider="openai")
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


@app.get("/check-for-new-product")
async def test_model(token: Annotated[str, Depends(oauth2_scheme)]):
    product_name = scrape_links()
    return {'message': product_name}

@app.post('/find-links')
def find_links(link: str, token: Annotated[str, Depends(oauth2_scheme)]):
    scrape_links()
    return {'message': 'link found'}

@app.post("/token")
async def authorise(form_data: Annotated[OAuth2PasswordRequestForm,Depends()]):
    user = form_data.username
    password = form_data.password
    if user != os.getenv("ADMIN") or password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": user, 'token_type': 'bearer'}
