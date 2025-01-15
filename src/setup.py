
import os
from dotenv import load_dotenv

from openai import OpenAI
load_dotenv()

openai_client = OpenAI()
openai_model="gpt-4o-mini"

host=os.getenv('POSTGRES_HOST', 'localhost')
database=os.getenv('POSTGRES_DB', "postgres")
user=os.getenv('POSTGRES_USER')
password=os.getenv('POSTGRES_PASSWORD')
port=os.getenv('POSTGRES_PORT', '5432')