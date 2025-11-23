import os
from dotenv import load_dotenv

load_dotenv()
openai_model = "gpt5-5.1-chat-latest"

host = os.getenv("POSTGRES_HOST", "localhost")
database = os.getenv("POSTGRES_DB", "postgres")
user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
port = os.getenv("POSTGRES_PORT", "7654")
