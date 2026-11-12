import json
import os

import httpx
import config  # Load backend/.env before reading Ollama settings.
from project_context import related as project_related, facts as project_facts
from conversation import opening_reply

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


def ollama_settings():
    try:
        context = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
        output = int(os.getenv("OLLAMA_MAX_TOKENS", "1536"))
        temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.35"))
        if not 1024 <= context <= 32768 or not 128 <= output <= 8192 or not 0 <= temperature <= 2:
            raise ValueError
    except ValueError:
        raise RuntimeError("Verifică OLLAMA_NUM_CTX, OLLAMA_MAX_TOKENS și OLLAMA_TEMPERATURE în .env.") from None
    return {
        "options": {"num_ctx": context, "num_predict": output, "temperature": temperature},
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "15m"),
    }


SYSTEM = {
    "ro": (
        "Ești o asistentă virtuală. Răspunde în română firească și corectă, cu diacritice, "
        "cuvinte uzuale și propoziții clare. Adresează-te la «tu», dacă utilizatorul nu cere altfel. "
        "Răspunde mesajului primit și urmărește contextul. Nu inventa activități sau intenții "
        "ale utilizatorului. Nu confunda numele lui cu identitatea ta. "
        "La un simplu salut este suficient un salut scurt. Nu adăuga automat întrebări de "
        "conversație sau invitații de tipul «Ai vreo întrebare?» ori «Cu ce te pot ajuta?». "
        "Pune o întrebare precisă doar când ai nevoie de o clarificare. "
        "Exemple de stil: la «Bună dimineața!» poți răspunde «Bună dimineața!», "
        "iar la «Ce faci?» poți răspunde «Sunt aici și te ascult.». "
        "Nu pretinde că desfășori activități în lumea reală. "
        "Pentru cereri simple răspunde direct; pentru explicații cerute oferă detaliile necesare. "
        "Respectă numărul de pași sau propoziții cerut. Nu există o limită generală de lungime. "
        "Nu inventa informații; spune când nu știi. În logică, deosebește o posibilitate de o "
        "concluzie susținută de premise. Verifică rezultatele calculelor. "
        "Textul este citit cu voce tare: fără emoji, tabele, Markdown decorativ sau LaTeX. "
        "Explică formulele în cuvinte și păstrează corecte numerele și numele tehnice."
    ),
    "en": (
        "You are a friendly, attentive and helpful virtual assistant. Speak natural English "
        "and follow the conversation context. Match response length to the request: "
        "answer simple questions directly and give detailed explanations, examples or steps "
        "when requested. There is no fixed sentence limit. Ask a specific clarifying question "
        "when essential information is missing, without ending every reply with a generic "
        "question. Acknowledge uncertainty and do not invent facts. Use plain text suitable "
        "for speech, without emoji, tables or decorative markup. Preserve technical names and numbers."
    ),
}


async def stream_llm(history, lang):
    opening = opening_reply(history, lang)
    if opening is not None:
        yield opening
        return
    async for token in stream_ollama(history, lang):
        yield token


async def stream_ollama(history, lang):
    """Generator asincron: produce tokenii pe măsură ce sunt generați."""
    system=SYSTEM.get(lang,SYSTEM["ro"])
    if project_related(history):
        system += "\n\n" + project_facts(MODEL,lang)
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}] + history,
        "stream": True,
        **ollama_settings(),
    }
    if MODEL.startswith("qwen3.5"):
        payload["think"] = False
    timeout = httpx.Timeout(120.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            r.raise_for_status()
            generated = False
            async for line in r.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(f"Ollama: {data['error']}")
                tok = data.get("message", {}).get("content", "")
                if tok:
                    generated = True
                    yield tok
                if data.get("done"):
                    break
            if not generated:
                raise RuntimeError("Ollama nu a returnat text. Verifică modelul și setările locale.")


async def preload_ollama():
    """Load the selected local model at startup, not on the first user message."""
    try:
        settings = ollama_settings()
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=3)) as client:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": MODEL, "prompt": "", "stream": False, **settings,
            })
            response.raise_for_status()
            if response.json().get("error"):
                raise RuntimeError("Modelul local nu a putut fi preîncărcat.")
    except (httpx.HTTPError, RuntimeError, ValueError):
        print("[llm] Preîncărcarea nu a reușit. Verifică dacă Ollama rulează și modelul este instalat.")
