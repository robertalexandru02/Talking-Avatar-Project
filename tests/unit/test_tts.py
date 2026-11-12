import asyncio
import io
import sys
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
import tts
import main

class AlignmentTests(unittest.TestCase):
    def test_expanded_text_chunks_keep_native_timing_across_pauses(self):
        spoken=[]
        def synth(text,**kwargs):
            spoken.append(text)
            yield SimpleNamespace(sample_rate=1000,audio_float_array=[0]*300,audio_int16_bytes=b'\x01\x02'*300,
                phoneme_alignments=[SimpleNamespace(phoneme='u',num_samples=300)])
        voice=SimpleNamespace(config=SimpleNamespace(sample_rate=1000),synthesize=synth)
        original='LLM TTS API '*30
        with patch.object(tts,'_load',return_value=voice):
            speech=tts._synth(original,'ro')
        self.assertGreater(len(spoken),1)
        self.assertTrue(all(len(piece)<=180 for piece in spoken))
        self.assertEqual(' '.join(spoken),' '.join(tts.prepare_romanian(original).split()))
        expected=tts.SPEECH_LEAD_MS+len(spoken)*300+(len(spoken)-1)*70
        with wave.open(io.BytesIO(speech.wav)) as audio:
            self.assertEqual(audio.getnframes(),expected)
        self.assertEqual(speech.visemes[-1]['t']+speech.visemes[-1]['d'],expected)

    def test_onset_padding_preserves_pcm_and_shifts_alignment(self):
        pcm=b'\x12\x34'*300
        chunk=SimpleNamespace(sample_rate=1000,audio_float_array=[0]*300,audio_int16_bytes=pcm,
            phoneme_alignments=[SimpleNamespace(phoneme=p,num_samples=n) for p,n in [('b',30),('u',270)]])
        voice=SimpleNamespace(config=SimpleNamespace(sample_rate=1000),synthesize=lambda *a,**kw:iter([chunk]))
        with patch.object(tts,'_load',return_value=voice):
            speech=tts._synth('Bună!','ro')
        with wave.open(io.BytesIO(speech.wav)) as audio:
            samples=audio.readframes(audio.getnframes())
        self.assertEqual(samples,b'\x00\x00'*tts.SPEECH_LEAD_MS+pcm)
        self.assertEqual(speech.visemes,[{'v':'REST','t':0,'d':120},{'v':'BMP','t':120,'d':30},{'v':'U','t':150,'d':270}])

    def test_ipa_vowels_closures_and_stress(self):
        self.assertEqual([tts.ipa_viseme(p) for p in ['a','o','ə','e','ɨ','u','b','f','ʃ','θ',' ']],
                         ['A','O','SCHWA','E','I','U','BMP','FV','SHCH','TH','REST'])
        self.assertIsNone(tts.ipa_viseme('ˈ'))

    def test_real_sample_offsets_and_stress_do_not_close_mouth(self):
        chunk = SimpleNamespace(sample_rate=1000, audio_float_array=[0]*300,
            phoneme_alignments=[SimpleNamespace(phoneme=p,num_samples=n)
                                for p,n in [('^',30),('ˈ',100),('a',20),('m',50),('$',100)]])
        timeline = tts.chunk_timeline(chunk, 500)
        self.assertEqual([v['t'] for v in timeline], [500,530,630,650,700])
        self.assertEqual([v['v'] for v in timeline], ['REST','A','A','BMP','REST'])
        self.assertEqual(timeline[-1]['t']+timeline[-1]['d'],800)
        chunk.phoneme_alignments = None
        self.assertIsNone(tts.chunk_timeline(chunk,0))

    def test_voice_selection_is_allowlisted(self):
        with self.assertRaises(ValueError):
            tts._load('ro','../../file')

class WorkerAlignmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_sends_native_alignment_and_selected_voice(self):
        out=io.BytesIO()
        with wave.open(out,'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(1000)
            wf.writeframes(b'\x00\x10'*300)
        native=[{'v':'REST','t':0,'d':50},{'v':'A','t':50,'d':250}]
        queue=asyncio.Queue()
        await queue.put([{'text':'Salut','ph':[('A_O',1)]}]); await queue.put(None)
        messages=[]
        async def send(message): messages.append(message)
        async def synth(text,lang,voice):
            self.assertEqual(voice,'sanda')
            return tts.Speech(out.getvalue(),native)
        with patch.object(tts,'synthesize',synth):
            await main.tts_worker(queue,send,'ro','sanda')
        speech=next(m for m in messages if m['type']=='speech')
        self.assertEqual(speech['visemes'],native)
        self.assertEqual(speech['alignment'],'piper')
