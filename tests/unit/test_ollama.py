import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import llm


class OllamaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"OLLAMA_NUM_CTX": "4096",
            "OLLAMA_MAX_TOKENS": "1536", "OLLAMA_TEMPERATURE": "0.6",
            "OLLAMA_KEEP_ALIVE": "15m"})
        env.start()
        self.addCleanup(env.stop)

    def client(self, handler):
        real = httpx.AsyncClient
        transport = httpx.MockTransport(handler)
        return patch.object(llm.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))

    async def test_gemma_stream_preserves_context_and_settings(self):
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, text=json.dumps({"message": {"content": "Salut"}}) + "\n" + json.dumps({"done": True}) + "\n")
        history = [{"role": "user", "content": "Ana"}, {"role": "assistant", "content": "Salut Ana"}, {"role": "user", "content": "Cum mă numesc?"}]
        with patch.object(llm, "MODEL", "gemma3:4b"), self.client(handler):
            output = [t async for t in llm.stream_ollama(history, "ro")]
        self.assertEqual(output, ["Salut"])
        payload = captured[0]
        self.assertNotIn("think", payload)
        self.assertEqual(payload["options"]["num_ctx"], 4096)
        self.assertEqual(payload["keep_alive"], "15m")
        self.assertEqual(payload["messages"][1:], history)
        self.assertEqual(payload["model"], "gemma3:4b")

    async def test_empty_output_is_reported(self):
        with self.client(lambda request: httpx.Response(200, text='{"done":true}\n')):
            with self.assertRaisesRegex(RuntimeError, "nu a returnat text"):
                _ = [t async for t in llm.stream_ollama([], "ro")]

    async def test_qwen35_disables_thinking_and_only_speaks_final_content(self):
        captured=[]
        def handler(request):
            captured.append(json.loads(request.content))
            events=[{'message':{'thinking':'internal reasoning','content':''}},
                    {'message':{'content':'Bună!'}},{'done':True}]
            return httpx.Response(200,text='\n'.join(json.dumps(event) for event in events))
        with patch.object(llm,'MODEL','qwen3.5:4b'),self.client(handler):
            output=[token async for token in llm.stream_ollama([{'role':'user','content':'Salut'}],'ro')]
        self.assertFalse(captured[0]['think'])
        self.assertEqual(output,['Bună!'])

    async def test_project_questions_include_local_facts_without_changing_history(self):
        captured=[]
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,text='{"message":{"content":"Prin viseme."},"done":true}\n')
        history=[{'role':'user','content':'Cum funcționează lip-sync în acest proiect?'}]
        with self.client(handler):
            _=[token async for token in llm.stream_ollama(history,'ro')]
        system=captured[0]['messages'][0]['content']
        self.assertIn('Date verificate despre aplicație',system)
        self.assertIn(llm.MODEL,system)
        self.assertEqual(captured[0]['messages'][1:],history)

    async def test_model_preloads_with_same_context(self):
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={"done": True})
        with self.client(handler):
            await llm.preload_ollama()
        self.assertEqual(captured[0]["prompt"], "")
        self.assertEqual(captured[0]["options"]["num_ctx"], 4096)

    async def test_invalid_settings_fail_before_network_request(self):
        with patch.dict(os.environ, {"OLLAMA_NUM_CTX": "bad"}), patch.object(llm.httpx, "AsyncClient") as client:
            with self.assertRaises(RuntimeError):
                _ = [t async for t in llm.stream_ollama([], "ro")]
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
