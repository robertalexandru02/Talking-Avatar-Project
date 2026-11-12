import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import asr

class TranscriptionTests(unittest.TestCase):
    def test_quiet_speech_retries_when_vad_discards_everything(self):
        model=Mock()
        model.transcribe.side_effect=[(iter([]),None),
            (iter([SimpleNamespace(text=' Salut!',no_speech_prob=.1,avg_logprob=-.2)]),None)]
        with patch('faster_whisper.decode_audio',return_value=np.full(6000,.01,dtype=np.float32)),patch.object(asr,'_model',model):
            self.assertEqual(asr.transcribe(b'audio','ro'),'Salut!')
        self.assertEqual(model.transcribe.call_count,2)
        self.assertFalse(model.transcribe.call_args_list[1].kwargs['vad_filter'])
        self.assertAlmostEqual(float(model.transcribe.call_args_list[0].args[0].max()),.08,places=4)

    def test_silence_never_reaches_whisper(self):
        model=Mock()
        with patch('faster_whisper.decode_audio',return_value=np.zeros(16000,dtype=np.float32)),patch.object(asr,'_model',model):
            self.assertEqual(asr.transcribe(b'audio','ro'),'')
        model.transcribe.assert_not_called()

    def test_fallback_filters_likely_non_speech(self):
        model=Mock()
        model.transcribe.side_effect=[(iter([]),None),
            (iter([SimpleNamespace(text=' invented',no_speech_prob=.9,avg_logprob=-1.4)]),None)]
        with patch('faster_whisper.decode_audio',return_value=np.full(6000,.01,dtype=np.float32)),patch.object(asr,'_model',model):
            self.assertEqual(asr.transcribe(b'audio','ro'),'')
