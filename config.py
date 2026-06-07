import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MIMO_API_KEY = os.getenv("MIMO_API_KEY")

client = OpenAI(
    api_key=MIMO_API_KEY,
    base_url="https://token-plan-sgp.xiaomimimo.com/v1"
)
