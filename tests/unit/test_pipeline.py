"""Run with backend/.venv/Scripts/python.exe -m unittest discover -s tests -v."""
import asyncio
import base64
import io
import sys
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import llm
import main
from fastapi.testclient import TestClient


def wav_bytes():
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"\x00\x10" * 2205)
    return out.getvalue()


async def reply(history, lang):
    for token in ("Salut ", "lume."):
        yield token


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def run_turn(self, generator=reply, synthesis=None, voice=None):
        messages = []
        history = []

        class Socket:
            async def send_json(self, obj):
                messages.append(obj)

        async def synth(text, lang, selected=None):
            return wav_bytes()

        with patch.object(main, "stream_llm", generator), patch.object(
                main.tts, "synthesize", synthesis or synth):
            message={"id": 7, "text": "Salut", "lang": "ro"}
            if voice:message['voice']=voice
            await main.run_turn(Socket(), history, message)
        return messages, history

    async def test_stream_audio_and_done_order(self):
        messages, history = await self.run_turn()
        self.assertEqual("".join(m["text"] for m in messages if m["type"] == "token"), "Salut lume.")
        speech = next(m for m in messages if m["type"] == "speech")
        self.assertEqual(base64.b64decode(speech["audio"]), wav_bytes())
        self.assertEqual(messages[-1]["type"], "done")
        self.assertTrue(all(m["turn"] == 7 for m in messages))
        self.assertEqual(history[-1]["content"], "Salut lume.")

    async def test_tts_failure_still_completes_text(self):
        async def broken(text, lang):
            raise RuntimeError("voice unavailable")
        messages, _ = await self.run_turn(synthesis=broken)
        error = next(m for m in messages if m["type"] == "error")
        self.assertFalse(error["fatal"])
        self.assertEqual(messages[-1]["type"], "done")

    async def test_sentence_context_preserved_past_eight_words_and_commas(self):
        sentence = "Bună ziua, pot să îți explic pe îndelete cum funcționează acest proiect."
        async def tokens(history, lang):
            for word in sentence.split():
                yield word + " "
        messages, _ = await self.run_turn(generator=tokens)
        spoken = [m["text"] for m in messages if m["type"] == "speech"]
        self.assertEqual(spoken, [sentence])

    async def test_abbreviation_does_not_break_sentence(self):
        sentence = "Dr. Popescu te poate ajuta."
        async def tokens(history, lang):
            for word in sentence.split():
                yield word + " "
        messages, _ = await self.run_turn(generator=tokens)
        self.assertEqual([m["text"] for m in messages if m["type"] == "speech"], [sentence])

    async def test_first_long_clause_is_spoken_before_llm_finishes(self):
        first = "Acesta este un exemplu de explicație suficient de lungă pentru a fi rostită separat în mod natural,"
        ready = asyncio.Event()
        async def tokens(history,lang):
            for word in first.split(): yield word+' '
            await asyncio.wait_for(ready.wait(),2)
            yield ' apoi continuăm explicația.'
        async def synth(text,lang):
            ready.set()
            return wav_bytes()
        messages,_=await self.run_turn(generator=tokens,synthesis=synth)
        self.assertEqual(next(m['text'] for m in messages if m['type']=='speech'),first)

    async def test_long_sentence_remains_bounded(self):
        async def tokens(history, lang):
            for _ in range(120):
                yield "cuvânt "
        messages, _ = await self.run_turn(generator=tokens)
        spoken = [m["text"] for m in messages if m["type"] == "speech"]
        self.assertGreater(len(spoken), 1)
        self.assertEqual(len(" ".join(spoken).split()), 120)
        self.assertTrue(all(len(text) <= 170 + 6 for text in spoken))

    async def test_liana_preserves_longer_sentence_context(self):
        async def tokens(history,lang):
            for _ in range(120):yield 'cuvânt '
        messages,_=await self.run_turn(generator=tokens,voice='liana')
        spoken=[m['text'] for m in messages if m['type']=='speech']
        self.assertTrue(any(len(text)>170 for text in spoken))
        self.assertTrue(all(len(text)<=main.MAX_CHARS+6 for text in spoken))
        self.assertEqual(len(' '.join(spoken).split()),120)

    async def test_generation_error_is_terminal(self):
        async def broken(history, lang):
            raise RuntimeError("model unavailable")
            yield  # Make this an async generator.
        messages, history = await self.run_turn(generator=broken)
        self.assertTrue(messages[-1]["fatal"])
        self.assertEqual(history, [])

    async def test_cancel_awaits_worker_and_no_done(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        messages = []

        async def tokens(history, lang):
            yield "Salut. "
            await asyncio.Event().wait()

        async def synth(text, lang):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        class Socket:
            async def send_json(self, obj):
                messages.append(obj)

        with patch.object(main, "stream_llm", tokens), patch.object(main.tts, "synthesize", synth):
            task = asyncio.create_task(main.run_turn(Socket(), [], {"id": 1, "text": "Salut"}))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(cancelled.is_set())
        self.assertNotIn("done", [m["type"] for m in messages])

    async def test_ollama_http_and_stream_errors(self):
        real_client = httpx.AsyncClient
        for status, content, error in ((404, b'{"error":"missing model"}', httpx.HTTPStatusError),
                                       (200, b'{"error":"load failed"}\n', RuntimeError)):
            transport = httpx.MockTransport(lambda request: httpx.Response(status, content=content))
            with patch.object(llm.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)):
                with self.assertRaises(error):
                    async for _ in llm.stream_ollama([], "ro"):
                        pass


class SocketTests(unittest.TestCase):
    def test_validation_and_connection_reuse(self):
        client = TestClient(main.app)
        with patch.object(main, "stream_llm", reply):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "chat", "id": 1, "text": "", "lang": "ro"})
                self.assertTrue(ws.receive_json()["fatal"])
                ws.send_json({"type": "stop"})
                ws.send_json({"type": "chat", "id": 2, "text": "Salut", "lang": "invalid"})
                self.assertEqual(ws.receive_json()["turn"], 2)


if __name__ == "__main__":
    unittest.main()
