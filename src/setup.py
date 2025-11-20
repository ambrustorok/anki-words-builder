import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("POSTGRES_HOST", "localhost")
database = os.getenv("POSTGRES_DB", "postgres")
user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
port = os.getenv("POSTGRES_PORT", "6543")
