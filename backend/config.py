"""Local configuration; backend/.env is never served by the frontend."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=False)

def public_config():
    return {
        "llm": "ollama",
        "model": os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        "tts": "piper",
        "voice": "Raluca / Lessac",
    }
