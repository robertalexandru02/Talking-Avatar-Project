"""Real Piper -> local Whisper transcription in Romanian and English; no cloud."""
import sys
import time
import io
import wave
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import asr
import tts

def run():
    for lang,text in [('ro','Bună ziua! Vreau să înțeleg cum funcționează animația personajului.'),
                      ('en','Hello! I would like to understand how this animation works.')]:
        speech=tts._synth(text,lang,'raluca')
        start=time.perf_counter();result=asr.transcribe(speech.wav,lang)
        print(f'{lang}: {time.perf_counter()-start:.2f}s; '+result.encode('ascii','backslashreplace').decode(),flush=True)
        assert len(result)>20,(lang,result)
        if lang=='ro':
            assert any(word in result.lower() for word in ['anima','personaj','func']),result
            with wave.open(io.BytesIO(speech.wav)) as source:
                params=source.getparams()
                samples=np.frombuffer(source.readframes(source.getnframes()),dtype=np.int16)
            quiet=io.BytesIO()
            with wave.open(quiet,'wb') as target:
                target.setparams(params);target.writeframes((samples*.025).astype(np.int16).tobytes())
            quiet_text=asr.transcribe(quiet.getvalue(),lang)
            assert any(word in quiet_text.lower() for word in ['anima','personaj','func']),quiet_text
            print('PASS: Romanian speech at 2.5 percent input volume',flush=True)
        else:assert any(word in result.lower() for word in ['animation','works','understand']),result

if __name__=='__main__':run()
