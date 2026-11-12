import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from conversation import opening_reply
import llm

class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def history(self,text):return [{'role':'user','content':text}]

    def test_exact_romanian_social_openings(self):
        self.assertEqual(opening_reply(self.history('Bună seara!'),'ro'),'Bună seara!')
        self.assertEqual(opening_reply(self.history('Buna! Cum ești astăzi?'),'ro'),'Bună! Sunt aici și te ascult.')
        self.assertEqual(opening_reply(self.history('Ce mai faci?'),'ro'),'Sunt aici și te ascult.')

    def test_substantive_requests_and_other_languages_reach_model(self):
        for text in ['Ce faci cu visemele?', 'Bună! Explică-mi proiectul.', 'Cum ești sigur că rezultatul este corect?', 'Ce faci? Explică-mi apoi streamingul.']:
            self.assertIsNone(opening_reply(self.history(text),'ro'))
        self.assertIsNone(opening_reply(self.history('Bună!'),'en'))

    async def test_opening_uses_normal_pipeline_without_llm_call(self):
        with patch.object(llm,'stream_ollama',side_effect=AssertionError('unneeded model call')):
            answer=''.join([token async for token in llm.stream_llm(self.history('Ce faci?'),'ro')])
        self.assertEqual(answer,'Sunt aici și te ascult.')

    async def test_general_answers_still_stream(self):
        async def model(history,lang):
            yield 'Text '
            yield 'generat.'
        with patch.object(llm,'stream_ollama',model):
            tokens=[token async for token in llm.stream_llm(self.history('Explică ploaia.'),'ro')]
        self.assertEqual(tokens,['Text ','generat.'])
