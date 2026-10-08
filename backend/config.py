import os

from dotenv import load_dotenv


load_dotenv()


OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "http://127.0.0.1:10531/v1"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "dummy"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "gpt-5.6-luna"
)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY"
)