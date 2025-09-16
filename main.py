from datetime import datetime, timedelta
from typing import Annotated
from fastapi import FastAPI, UploadFile, Depends, HTTPException,status, Form
from pydantic import BaseModel
from sqlalchemy import create_engine
from db.models.base import Base
import os
import dotenv
import jwt
from jwt.exceptions import InvalidTokenError
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from utils.util import scape_format_embed, retrieve, scrape_links, define_message_intent
dotenv.load_dotenv()


app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

origins = [
    # "http://localhost:3000",
    # "https://artistic-chatbot-frontend.vercel.app",
    "*"
]
variable_origin = os.getenv("ORIGIN")
# if variable_origin:
#     origins.append(str(variable_origin))
print(f"CORS origins: {origins}")
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

class SystemMessageModel(BaseModel):
    message: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_admin_user(token: Annotated[str,Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        password = payload.get("password")
        if username is None or password is None:
            raise credentials_exception
        admin = os.getenv("ADMIN")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if username == admin and password == admin_password:
            return username
        else:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception



@app.get("/")
async def root():
    return {"message": "hello world"}


@app.get("/db_init")
async def db_init(token: Annotated[str, Depends(get_admin_user)]):
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
    elif 'ИСПОЛЬЗОВАТЬ_RAG' in intent:
        print('ИСПОЛЬЗОВАТЬ_RAG')
        docs_content = retrieve(query.message)
        message = [
            SystemMessage(content=f'{system_prompt},контекст: {docs_content} , История переписки: {query.history}'),
            HumanMessage(content=query.message)
        ]
    else:
        print('ОЦЕНИТЬ_ЛИДА')
        with open('lead_discovery_prompt.txt', 'r') as f:
            system_prompt = f.read()
        message = [
            SystemMessage(content=f'{system_prompt}, История переписки: {query.history}'),
            HumanMessage(content=query.message)
        ]

    model = init_chat_model("gpt-5", model_provider="openai")
    response = model.invoke(message)
    print(response.usage_metadata)
    return response.text()

@app.post("/upload-site-map")
async def upload_file(file: UploadFile, token: Annotated[str, Depends(get_admin_user)]):
    file_read = await file.read()
    text_file = file_read.decode("utf-8")
    site_map = text_file.split("\n")
    for site in site_map:
        scape_format_embed(site)
    return {
        'response':'upload success',
    }

@app.get("/check-for-new-product")
async def test_model(token: Annotated[str, Depends(get_admin_user)]):
    product_name = scrape_links()
    return {'message': product_name}

@app.post('/find-links')
def find_links(token: Annotated[str, Depends(get_admin_user)]):
    scrape_links()
    return {'message': 'link found'}

@app.post("/token")
async def authorise(form_data: Annotated[OAuth2PasswordRequestForm,Depends()]):
    user = form_data.username
    password = form_data.password
    if user != os.getenv("ADMIN") and password != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = jwt.encode({'username': user, 'password': password}, SECRET_KEY, algorithm='HS256')
    return {"access_token": token, 'token_type': 'bearer'}


@app.post("/edit-system-message")
async def edit_system_message(
        token: Annotated[str, Depends(get_admin_user)],
        message: Annotated[str,Form()],
        label: Annotated[str,Form()],
):
    # Define mapping of prompt labels to file names
    file_mapping = {
        'System Message': 'system_message.txt',
        'Lead Discovery': 'lead_discovery_prompt.txt',
        'Knowledge Base': 'use_rag_prompt.txt'
    }

    # Get the appropriate filename
    filename = file_mapping.get(label)

    if not filename:
        raise HTTPException(status_code=400, detail=f"Invalid prompt type: {label}")

    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(message)

        return {'message': f'{label} updated successfully', 'file': filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing to file: {str(e)}")


@app.get('/get-system-message')
async def get_system_message(token: Annotated[str, Depends(get_admin_user)]):
    with open('system_message.txt', 'r', encoding='utf-8') as file:
        system_message = file.read()
    with open('lead_discovery_prompt.txt', 'r', encoding='utf-8') as file:
        lead_discovery_prompt = file.read()
    with open('use-rag-prompt.txt', 'r', encoding='utf-8') as file:
        use_rag_prompt = file.read()

    return {'system_message': system_message,
            'lead_discovery_prompt': lead_discovery_prompt,
            'use_rag_prompt': use_rag_prompt
            }
