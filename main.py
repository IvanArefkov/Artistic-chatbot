from datetime import datetime, timedelta
from typing import Annotated
from fastapi import FastAPI, UploadFile, Depends, HTTPException,status, Form, Request
from pydantic import BaseModel
from sqlalchemy import create_engine
from db.models.base import Base
import requests
import os
import dotenv
import jwt
from jwt.exceptions import InvalidTokenError
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from utils.util import scape_format_embed, retrieve, scrape_links, define_message_intent
from sqlalchemy.orm import Session
from sqlalchemy import select
from db.models.base import ChatMessage,ChatSession
from telegram import Bot

dotenv.load_dotenv()

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

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

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

engine = create_engine(f"sqlite+{TURSO_DATABASE_URL}?secure=true", connect_args={
    "auth_token": os.getenv("TURSO_AUTH_TOKEN"),
})

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

def prompts():
    with open('prompts/use_rag_prompt.txt') as f:
        intent_prompt = f.read()
    with open('prompts/system_message.txt', 'r') as f:
        system_prompt = f.read()
    return intent_prompt, system_prompt

def compile_ai_request(intent, user_message):
    intent_prompt, system_prompt = prompts()
    if "НЕ_ИСПОЛЬЗОВАТЬ_RAG" in intent:
        print('НЕ_ИСПОЛЬЗОВАТЬ_RAG')
        message = [
            SystemMessage(content=f'{system_prompt}, История переписки: {user_message}'),
            HumanMessage(content=user_message)
        ]
    else:
        print('ИСПОЛЬЗОВАТЬ_RAG')
        docs_content = retrieve(user_message)
        message = [
            SystemMessage(content=f'{system_prompt},контекст: {docs_content} , История переписки: {user_message}'),
            HumanMessage(content=user_message)
        ]
    return message

@app.post("/chat")
async def chat(query: UserQuery):
    session = Session(engine)
    stmt = select(ChatSession).where(ChatSession.id == query.session_id)
    chat_session = session.execute(stmt).scalar_one_or_none()
    if chat_session:
        session_id = chat_session.id
    else:
        session_id = query.session_id
        chat_session = ChatSession(id=session_id)
        session.add(chat_session)
    user_chat_message = ChatMessage(
        session_id=session_id,
        sender="User",
        content=query.message,
    )
    session.add(user_chat_message)
    intent_prompt, system_prompt = prompts()
    intent = define_message_intent(message=query.message,prompt=intent_prompt)
    message = compile_ai_request(intent, query.message)
    model = init_chat_model("claude-sonnet-4-20250514", model_provider="anthropic")
    response = model.invoke(message)
    ai_chat_message = ChatMessage(
        session_id=session_id,
        sender="AI",
        content=response.text()
    )
    session.add(ai_chat_message)
    session.commit()
    session.close()
    print(response.response_metadata)
    return response.text()

@app.post('/webhook/telegram-chat')
async def telegram_webhook(request: Request):
    update_data = await request.json()
    print(update_data)
    if "message" in update_data:
        chat_id = update_data["message"]["chat"]["id"]
        user_message = update_data["message"]["text"]
        # user_id = update_data["message"]["from"]["id"]
        intent_prompt, system_prompt = prompts()
        intent = define_message_intent(message=user_message, prompt=intent_prompt)
        message = compile_ai_request(intent, user_message)
        model = init_chat_model("claude-sonnet-4-20250514", model_provider="anthropic")
        response = model.invoke(message)
        # Bot handles first message
        await bot.send_message(chat_id=chat_id, text=response.text())
    return {"status": "ok"}

def send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    response = requests.post(url, json=payload)
    return response.json()

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
        'System Message': 'prompts/system_message.txt',
        'Knowledge Base': 'prompts/use_rag_prompt.txt'
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
    with open('prompts/system_message.txt', 'r', encoding='utf-8') as file:
        system_message = file.read()
    with open('prompts/use_rag_prompt.txt', 'r', encoding='utf-8') as file:
        use_rag_prompt = file.read()

    return {'system_message': system_message,
            'use_rag_prompt': use_rag_prompt
            }


@app.get('/get-sessions')
async def get_sessions(token: Annotated[str, Depends(get_admin_user)]):
    sessions = Session(engine)
    stmt = select(ChatSession)
    result = sessions.execute(stmt)
    chat_sessions = result.scalars().all()  # Get all session objects

    sessions_data = []
    for session in chat_sessions:
        sessions_data.append({
            "id": session.id,
            "created_at": session.created_at.isoformat() if hasattr(session, 'created_at') else None,
        })

    sessions.close()  #
    return  sessions_data

@app.get('/get-chat/{session_id}')
async def get_chat(session_id: str ,token: Annotated[str, Depends(get_admin_user)]):
    sessions = Session(engine)
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    session = sessions.execute(stmt)
    chat_messages = session.scalars().all()
    sessions.close()
    chats = []
    for chat_message in chat_messages:
        chats.append({
            "id": chat_message.id,
            "sender": chat_message.sender,
            "content": chat_message.content,
            "created_at": chat_message.created_at.isoformat(),
        })
    return chats
