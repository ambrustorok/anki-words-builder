
import os
from dotenv import load_dotenv

from openai import OpenAI
load_dotenv()

openai_client = OpenAI()
openai_model="gpt-4o-mini"

host=os.getenv('DB_HOST', 'localhost')
database=os.getenv('DB_NAME', "postgres")
user=os.getenv('DB_USER')
password=os.getenv('DB_PASSWORD')
port=os.getenv('DB_PORT', '5432')
