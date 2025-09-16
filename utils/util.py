from langchain_community.document_loaders import WebBaseLoader
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from bs4 import BeautifulSoup as bs
import requests

import chromadb
import os

def scrape_links():
    response = requests.get(os.environ.get('CATALOG_PAGE_URL'))
    html_content = response.content
    soup = bs(html_content, 'html.parser')
    all_links = soup.find_all('a', class_='p-card__img')
    links_list = [link.get('href') for link in all_links if link.has_attr('href')]
    with open('site-map.txt','r') as f:
        file_text = f.read()
        for link in links_list:
            if link not in file_text.splitlines():
                print(link, 'not found')
                scape_format_embed(link)


def scape_format_embed(link: str):
    loader = WebBaseLoader(f'{link}')
    docs = loader.load()
    product_name = docs[0].metadata['title']
    path = f'formated_product_descriptions/{product_name}.txt'
    print(f"Processing {product_name}")
    try:
        with open(path,'r') as file:
            if len(file.read()) > 0:
                print(f'file {product_name} already processed')
                return product_name
    except FileNotFoundError:
        print('file not found, creating file')
    with open(f"{path}", "w") as file:
        print(f'formatting {product_name}')
        with open('formatting_instructions.txt', 'r') as instruction:
            formatting_instructions = instruction.read()

        model = init_chat_model("gpt-5-mini", model_provider='openai')
        message = [
            SystemMessage(content=formatting_instructions),
            HumanMessage(content=docs[0].page_content),
        ]
        response = model.invoke(message)

        # Write to file (overwrites if exists)
        file.write(response.text())

    process_text_to_chrome(text=response.text(), metadata={'product_name': product_name})
    return product_name


def connect_chromadb():
    chroma_client = chromadb.CloudClient(
        api_key=f'{os.environ["CHROMA_CLOUD_API"]}',
        tenant=f'{os.environ["CHROMA_TENANT"]}',
        database='Artistic-vector-db'
    )
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(
        client=chroma_client,
        collection_name='my_collection',
        embedding_function=embeddings
    )
    return vector_store

# Define application steps
def retrieve(query: str):
    vector_store = connect_chromadb()
    retrieved_docs = vector_store.similarity_search(query)
    docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)
    return docs_content

def process_text_to_chrome(text: str, metadata: dict):
    vector_store = connect_chromadb()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_splits = text_splitter.split_text(text=text)
    metadata_list = [metadata for _ in all_splits]
    vector_store.add_texts(texts=all_splits, metadatas=metadata_list)

def define_message_intent(message: str, prompt: str):
    model = init_chat_model("gpt-5-nano", model_provider='openai')
    model_message = [
        SystemMessage(content=prompt),
        HumanMessage(content=message),
    ]
    response = model.invoke(model_message)
    return response.text()
