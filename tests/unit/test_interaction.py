import io
import sys
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import main
import tts

class InteractionTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(main.app)

    def test_microphone_bytes_go_to_local_transcriber(self):
        with patch.object(main.asr,'transcribe',return_value='Bună ziua!') as transcribe:
            response=self.client.post('/api/transcribe?lang=ro',content=b'test-audio',headers={'Content-Type':'audio/webm'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['text'],'Bună ziua!')
        transcribe.assert_called_once_with(b'test-audio','ro')

    def test_microphone_validation_and_missing_model(self):
        self.assertEqual(self.client.post('/api/transcribe',content=b'').status_code,400)
        self.assertEqual(self.client.post('/api/transcribe?lang=xx',content=b'audio').status_code,400)
        self.assertEqual(self.client.post('/api/transcribe',content=b'x'*(8*1024*1024+1)).status_code,413)
        with patch.object(main.asr,'transcribe',side_effect=RuntimeError('model missing')):
            self.assertEqual(self.client.post('/api/transcribe',content=b'audio').status_code,503)

    def test_articulation_sample_has_native_timeline(self):
        out=io.BytesIO()
        with wave.open(out,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050);wav.writeframes(b'\0\0'*100)
        timeline=[{'v':'BMP','t':0,'d':4}]
        async def synth(text,lang,voice):
            self.assertEqual(lang,'ro');self.assertEqual(voice,'raluca')
            return tts.Speech(out.getvalue(),timeline)
        with patch.object(tts,'synthesize',synth):
            response=self.client.post('/api/speech-sample',json={'sample':'lips','lang':'ro','voice':'raluca'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['visemes'],timeline)
        self.assertEqual(response.json()['alignment'],'piper')

    def test_articulation_sample_rejects_arbitrary_text_or_voice(self):
        for data in [[],{'sample':'unknown'},{'sample':'lips','voice':'../../x'}, {'sample':{},'voice':'raluca'}]:
            self.assertEqual(self.client.post('/api/speech-sample',json=data).status_code,400)
