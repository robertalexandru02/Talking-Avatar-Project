"""Optional real CPU synthesis check for the installed voices and alignments."""
import io
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import tts

def run():
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    text = 'Bună! Mă bucur să vorbim. Pot să îți explic proiectul pas cu pas.'
    for voice in tts.ROMANIAN_VOICES:
        for index, opening in enumerate(['Bună!', 'Bună seara!', 'Bine ai venit!']):
            onset=tts._synth(opening,'ro',voice)
            with wave.open(io.BytesIO(onset.wav)) as wav:
                lead=round(wav.getframerate()*tts.SPEECH_LEAD_MS/1000)
                assert wav.readframes(lead)==b'\x00\x00'*lead,voice
            first=next(v for v in onset.visemes if v['v']!='REST')
            assert first['v']=='BMP' and first['t']>=tts.SPEECH_LEAD_MS,(voice,opening,first)
            (artifacts/f'onset-{voice}-{index}.wav').write_bytes(onset.wav)
        speech = tts._synth(text, 'ro', voice)
        assert speech.visemes, voice
        with wave.open(io.BytesIO(speech.wav)) as wav:
            duration = wav.getnframes() * 1000 / wav.getframerate()
        last_end = speech.visemes[-1]['t'] + speech.visemes[-1]['d']
        assert abs(last_end - duration) < 25, (voice,last_end,duration)
        assert all(a['t'] <= b['t'] for a,b in zip(speech.visemes,speech.visemes[1:])), voice
        assert {'BMP','U','SCHWA','I'} <= {v['v'] for v in speech.visemes}, voice
        (artifacts / f'voice-{voice}.wav').write_bytes(speech.wav)
        print(f'PASS: {voice}, {len(speech.visemes)} sample-aligned visemes, {duration/1000:.2f}s audio',flush=True)
    speech = tts._synth('Hello! My voice follows the animation.', 'en')
    assert speech.visemes
    print('PASS: English Lessac sample alignments',flush=True)

if __name__ == '__main__':
    run()
