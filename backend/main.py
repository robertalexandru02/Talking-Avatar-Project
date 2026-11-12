import asyncio
import base64
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.staticfiles import StaticFiles

import tts
import asr
from llm import stream_llm, preload_ollama
from config import public_config
from phonemes import REST, word_to_visemes

WORD = re.compile(r"\s*(\S+)\s")      # un cuvânt e complet când e urmat de spațiu
MD_CHARS = re.compile(r"[*_#`>]")
HARD, SOFT = ".!?…", ",;:"
MAX_CHARS = 420                       # limită de protecție pentru propoziții foarte lungi
ABBREVIATIONS = {"dr.", "dl.", "dna.", "nr.", "str.", "bd.", "prof.", "ing.",
                 "mr.", "mrs.", "ms.", "e.g.", "i.e."}


@asynccontextmanager
async def lifespan(app):
    await asyncio.gather(asyncio.to_thread(tts.preload), preload_ollama())
    yield


app = FastAPI(lifespan=lifespan)


def build_timeline(phs, start_ms, end_ms):
    """Scalează duratele relative ale visemelor pe fereastra reală de vorbire."""
    total = sum(w for _, w in phs) or 1.0
    scale = (end_ms - start_ms) / total
    t, out = start_ms, []
    for g, w in phs:
        d = w * scale
        out.append({"v": g, "t": round(t), "d": round(d)})
        t += d
    return out


async def tts_worker(q, send, lang, voice=None):
    """Modulul TTS + Foneme: consumă fragmente, produce audio + viseme."""
    try:
        while (frag := await q.get()) is not None:
            text = " ".join(w["text"] for w in frag)
            if not re.search(r"\w", text):
                continue
            phs = [p for w in frag for p in w["ph"]]
            while phs and phs[-1][0] == REST:
                phs.pop()
            await send({"type": "status", "stage": "speech"})
            result = await tts.synthesize(text, lang, voice) if voice else await tts.synthesize(text, lang)
            wav = result.wav if isinstance(result, tts.Speech) else result
            start, end = tts.speech_window_ms(wav)
            aligned = isinstance(result, tts.Speech) and result.visemes is not None
            await send({
                "type": "speech",
                "text": text,
                "audio": base64.b64encode(wav).decode(),
                "visemes": result.visemes if aligned else build_timeline(phs, start, end),
                "alignment": "piper" if aligned else "estimated",
            })
    except Exception as e:  # noqa: BLE001
        await send({"type": "error", "text": f"TTS: {e}", "fatal": False})


async def run_turn(ws, history, msg):
    lang = msg.get("lang", "ro")
    turn = msg.get("id")
    lock = asyncio.Lock()

    async def send(obj):
        async with lock:
            await ws.send_json({**obj, "turn": turn})

    history.append({"role": "user", "content": msg["text"]})
    q: asyncio.Queue = asyncio.Queue()
    worker = asyncio.create_task(tts_worker(q, send, lang, msg.get("voice")))
    reply, buf, frag = "", "", []
    first_fragment = True
    # The older Raluca/Sanda models lose articulation on long input; Liana has
    # long-sentence training and can retain more context for intonation.
    short_voice = lang == "ro" and msg.get("voice", "raluca") != "liana"
    max_chars = 170 if short_voice else MAX_CHARS
    clause_chars = 110 if short_voice else 240

    def add_word(raw):
        """Foneme -> viseme pentru cuvântul abia terminat (în paralel cu generarea).
        Returnează True dacă fragmentul trebuie trimis la TTS."""
        raw = MD_CHARS.sub("", raw)
        if not raw.strip():
            return False
        m = re.match(r"^\W*(.*?)(\W*)$", raw)
        core, tail = m.group(1), m.group(2)
        end = tail.strip("\"'”»)")[-1:]
        gap = 1.6 if end and end in HARD else 0.9 if end and end in SOFT else 0.25
        frag.append({"text": raw, "ph": word_to_visemes(core, lang) + [(REST, gap)]})
        size = sum(len(w["text"]) + 1 for w in frag)
        sentence_end = bool(end and end in HARD and raw.lower() not in ABBREVIATIONS)
        # Preserve sentence context for prosody; split long clauses only as a fallback.
        return sentence_end or bool(end and end in SOFT and size >= (90 if first_fragment else clause_chars)) or size >= max_chars

    async def flush():
        nonlocal first_fragment
        if frag:
            await q.put(list(frag))
            frag.clear()
            first_fragment = False

    try:
        await send({"type": "status", "stage": "generating"})
        async for tok in stream_llm(history, lang):
            reply += tok
            await send({"type": "token", "text": tok})        # text către UI imediat
            buf += tok
            while (m := WORD.match(buf)):
                raw, buf = m.group(1), buf[m.end():]
                if add_word(raw):
                    await flush()
        if buf.strip():
            add_word(buf.strip())
        await flush()
        await q.put(None)
        await worker
        await send({"type": "done"})
    except httpx.HTTPError as e:
        await send({"type": "error", "text": f"Nu pot contacta serviciul LLM: {e}", "fatal": True})
    except Exception as e:  # noqa: BLE001
        await send({"type": "error", "text": f"Generare: {e}", "fatal": True})
    finally:
        if not worker.done():
            worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        if reply:
            history.append({"role": "assistant", "content": reply})
        else:
            history.pop()
        history[:] = history[-20:]


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    history, task = [], None

    async def cancel():
        nonlocal task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001
                pass
        task = None

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "stop":
                await cancel()
            elif msg.get("type") == "chat":
                await cancel()
                if (not isinstance(msg.get("text"), str)
                        or not 0 < len(msg["text"].strip()) <= 4000
                        or msg.get("lang", "ro") not in ("ro", "en")
                        or msg.get("voice") not in (None, *tts.ROMANIAN_VOICES)
                        or type(msg.get("id")) is not int):
                    await ws.send_json({"type": "error", "turn": msg.get("id"),
                                        "text": "Mesaj invalid (maxim 4000 de caractere, limba ro/en).",
                                        "fatal": True})
                    continue
                task = asyncio.create_task(run_turn(ws, history, msg))
    except WebSocketDisconnect:
        await cancel()


@app.get("/api/config")
def get_config():
    return public_config()


@app.post("/api/transcribe")
async def transcribe_audio(request: Request, lang: str = "ro"):
    if lang not in ("ro", "en"):
        raise HTTPException(400, "Limba trebuie să fie ro sau en.")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 8 * 1024 * 1024:
            raise HTTPException(413, "Înregistrarea este prea mare (maximum 8 MB).")
        chunks.append(chunk)
    if not size:
        raise HTTPException(400, "Înregistrarea este goală.")
    try:
        text = await asyncio.to_thread(asr.transcribe, b"".join(chunks), lang)
        return {"text": text, "language": lang}
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        raise HTTPException(400, "Nu pot decoda înregistrarea audio.") from error


SPEECH_SAMPLES = {
    "lips": {"ro":"Mama pune pâinea pe masă. Bine, putem începe!", "en":"My mum makes the best blueberry pie."},
    "vowels": {"ro":"Ana are mere. Eu văd un lup și o floare. Îți spun: a, e, i, o, u.", "en":"We see a blue moon over the ocean."},
    "numbers": {"ro":"Astăzi testăm trei exemple, douăzeci și cinci de particule și o sută patruzeci la sută.", "en":"Today we test three examples and one hundred forty percent."},
    "technical": {"ro":"Modelul LLM generează text, iar TTS produce vocea. Luminozitatea este 140%, animația rulează la 60 FPS, cu un timp de 20 ms.", "en":"The LLM generates text and TTS produces speech. Brightness is 140 percent, at 60 frames per second."},
}

@app.post("/api/speech-sample")
async def speech_sample(request: Request):
    try:
        data = await request.json()
    except ValueError as error:
        raise HTTPException(400, "Cerere invalidă.") from error
    if not isinstance(data, dict):
        raise HTTPException(400, "Cerere invalidă.")
    sample_id, lang, voice = data.get("sample"), data.get("lang", "ro"), data.get("voice", "raluca")
    if sample_id not in tuple(SPEECH_SAMPLES) or lang not in ("ro", "en") or voice not in tuple(tts.ROMANIAN_VOICES):
        raise HTTPException(400, "Test de articulare invalid.")
    try:
        result = await tts.synthesize(SPEECH_SAMPLES[sample_id][lang], lang, voice)
    except Exception as error:
        raise HTTPException(503, f"Vocea nu este disponibilă: {error}") from error
    return {"text": SPEECH_SAMPLES[sample_id][lang], "audio": base64.b64encode(result.wav).decode(),
            "visemes": result.visemes or [], "alignment": "piper" if result.visemes else "amplitude"}


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
