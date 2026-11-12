"""Optional real local Ollama/Piper latency and articulation endpoint checks."""
import asyncio
import base64
import io
import json
import sys
import time
import wave
from pathlib import Path
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import main
import tts

async def run():
    await asyncio.to_thread(tts.preload)
    await main.preload_ollama()
    start=time.perf_counter();first_text=None;first_audio=None;clips=[]
    class Socket:
        async def send_json(self,message):
            nonlocal first_text,first_audio
            if message['type']=='token' and first_text is None:first_text=time.perf_counter()-start
            if message['type']=='speech':
                if first_audio is None:first_audio=time.perf_counter()-start
                assert message['alignment']=='piper',message
                with wave.open(io.BytesIO(base64.b64decode(message['audio']))) as audio:
                    duration=audio.getnframes()*1000/audio.getframerate()
                assert all(v['t']+v['d']<=duration+25 for v in message['visemes'])
                clips.append(message)
            if message['type']=='error':raise AssertionError(message['text'])
    await main.run_turn(Socket(),[],{'id':1,'lang':'ro','voice':'raluca','text':'Răspunde exact cu o propoziție scurtă: ce este un avatar 3D?'})
    assert first_text is not None and first_audio is not None and clips
    metrics={'first_text_s':round(first_text,3),'first_wav_s':round(first_audio,3),'total_s':round(time.perf_counter()-start,3),'clips':len(clips)}
    folder=ROOT/'artifacts';folder.mkdir(exist_ok=True)
    (folder/'pipeline-performance.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics),flush=True)
    client=TestClient(main.app)
    for sample in main.SPEECH_SAMPLES:
        response=client.post('/api/speech-sample',json={'sample':sample,'lang':'ro','voice':'raluca'})
        assert response.status_code==200,response.text
        assert response.json()['alignment']=='piper'
    print('PASS: real pipeline and all native-aligned articulation samples',flush=True)

if __name__=='__main__':asyncio.run(run())
