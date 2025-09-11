from fastapi import FastAPI, UploadFile
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pydantic import BaseModel
from sqlalchemy import create_engine
from db.models.base import Base
import os
import dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_chroma import Chroma
import chromadb
from langchain_community.document_loaders import WebBaseLoader
from fastapi.middleware.cors import CORSMiddleware

dotenv.load_dotenv()
app = FastAPI()
origins = [
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = create_engine("postgresql://chatbot_user:chatbot_pass@localhost:5432/chatbot_db", echo=True)
def connect_chromadb():
    chroma_client = chromadb.HttpClient(host=os.getenv("CHROMADB_HOST"),port=8001)
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(
        client=chroma_client,
        collection_name='my_collection',
        embedding_function=embeddings
    )
    return vector_store

class User(BaseModel):
    username: str
    email: str
    disabled: bool

class UserQuery(BaseModel):
    message: str


# Define application steps
def retrieve(query: str):
    vector_store = connect_chromadb()
    retrieved_docs = vector_store.similarity_search(query)
    docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)
    return docs_content

@app.get("/")
async def root():
    return {"message": "hello world"}


@app.get("/db_init")
async def db_init():
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

@app.post("/upload-file")
async def upload_file(file: UploadFile):
    file_read = await file.read()
    text_file = file_read.decode("utf-8")
    vector_store = connect_chromadb()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=200)
    all_splits = text_splitter.split_text(text=text_file)
    vector_store.add_texts(all_splits)

    return {
        'response':'upload success',
    }

@app.get("/scrape")
async def test_model():
    # model = init_chat_model("gpt-5-mini", model_provider='openai')
    loader = WebBaseLoader('https://artistic-co.ru/product/dr-arrivo-ghost-euro/')
    docs = loader.load()
    print(docs)
    # response = model.invoke([HumanMessage(content='Hi, my name is Ivan')])
    return
