import os
from sqlalchemy import create_engine
import dotenv

dotenv.load_dotenv()
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

engine = create_engine(f"sqlite+{TURSO_DATABASE_URL}?secure=true", connect_args={
    "auth_token": os.getenv("TURSO_AUTH_TOKEN"),
})
