import gradio as gr
import os
import tempfile
import numpy as np
import soundfile as sf
import os
from dotenv import load_dotenv
from openai import OpenAI
import random
import os
import uuid
import random
import tempfile
import psycopg2
import genanki
import soundfile as sf
import re

from setup import openai_model, host, database, user, password, port


def save_audio_to_postgres(text, audio_binary):
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port,
    )
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS audio_files (
            id SERIAL PRIMARY KEY,
            text TEXT,
            audio_data BYTEA
        )"""
    )
    cur.execute("INSERT INTO audio_files (text, audio_data) VALUES (%s, %s)", 
                (text, psycopg2.Binary(audio_binary)))
    conn.commit()
    cur.close()
    conn.close()