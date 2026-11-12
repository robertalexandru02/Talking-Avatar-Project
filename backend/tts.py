"""TTS local cu Piper: text -> WAV + fereastra de vorbire (fără liniștea de la capete)."""
import asyncio
import io
import wave
import unicodedata
import threading
import os
from dataclasses import dataclass
from array import array
from pathlib import Path
import config  # Load .env before selecting voice quality.
from spoken_romanian import prepare as prepare_romanian, short_pieces

VOICE_DIR = Path(__file__).parent / "voices"
VOICE_FILES = {"ro": "ro_RO-raluca-high.onnx", "en": "en_US-lessac-medium.onnx"}
ROMANIAN_VOICES = {"liana": "ro_RO-liana-high.onnx", "raluca": VOICE_FILES["ro"],
                   "sanda": "ro_RO-sanda-medium.onnx"}
_voices = {}
_load_lock = threading.Lock()
# eSpeak's current voice is process-global; concurrent turns/previews can race.
_synthesis_lock = threading.Lock()
SPEECH_LEAD_MS = 120


@dataclass
class Speech:
    wav: bytes
    visemes: list | None


def ipa_viseme(phoneme):
    """Map the phonemes actually pronounced by Piper, including RO vowels."""
    if phoneme in ("ˈ", "ˌ", "ː", "ˑ", "ʲ", "ʰ"):
        return None
    for symbols, group in [("aɑɐ", "A"), ("oɔ", "O"), ("əʌɜ", "SCHWA"),
                           ("eɛæ", "E"), ("iɪɨɯj", "I"), ("uʊw", "U"),
                           ("bmp", "BMP"), ("fv", "FV"), ("ʃʒʧʤ", "SHCH"), ("θð", "TH")]:
        if any(char in symbols for char in phoneme):
            return group
    if any(char.isalpha() for char in phoneme):
        return "LDTNS"
    return "REST"


def chunk_timeline(chunk, offset_samples):
    """Use VITS sample alignments; never distribute letters uniformly over speech."""
    if not chunk.phoneme_alignments:
        return None
    total = sum(int(a.num_samples) for a in chunk.phoneme_alignments)
    if abs(total - len(chunk.audio_float_array)) > 512:
        return None
    out, cursor, previous = [], offset_samples, "REST"
    for index, alignment in enumerate(chunk.phoneme_alignments):
        count = int(alignment.num_samples)
        group = ipa_viseme(alignment.phoneme)
        if group is None:
            group = previous
            # eSpeak places stress markers before a vowel; their VITS duration
            # belongs to that upcoming articulation, not the preceding consonant.
            if alignment.phoneme in ("ˈ", "ˌ"):
                group = next((candidate for item in chunk.phoneme_alignments[index + 1:]
                              if (candidate := ipa_viseme(item.phoneme)) is not None), previous)
        previous = group
        if count > 0:
            start = round(cursor * 1000 / chunk.sample_rate)
            end = round((cursor + count) * 1000 / chunk.sample_rate)
            out.append({"v": group, "t": start, "d": max(1, end - start)})
        cursor += count
    return out


def _load(lang, selected=None):
    filename = ROMANIAN_VOICES.get(selected or "raluca") if lang == "ro" else VOICE_FILES["en"]
    if lang == "ro" and selected == "liana":
        quality = os.getenv("PIPER_LIANA_QUALITY", "high")
        if quality not in ("medium", "high"):
            raise ValueError("PIPER_LIANA_QUALITY trebuie să fie medium sau high.")
        filename = f"ro_RO-liana-{quality}.onnx"
    if not filename:
        raise ValueError("Voce română necunoscută.")
    with _load_lock:
        if filename in _voices:
            return _voices[filename]
        from piper import PiperVoice
        path = VOICE_DIR / filename
        if not path.exists():
            raise RuntimeError(f"Lipsește vocea {path.name}. Rulează: python download_voices.py")
        _voices[filename] = PiperVoice.load(str(path), include_alignments=True)
        return _voices[filename]


def preload():
    for lang, selected in [("ro", "raluca"), ("ro", "liana"), ("en", None)]:
        try:
            _load(lang, selected)
        except Exception as e:  # noqa: BLE001
            print(f"[tts] {lang}: {e}")


def _synth(text, lang, selected=None):
    with _synthesis_lock:
        return _synth_serial(text, lang, selected)


def _synth_serial(text, lang, selected=None):
    voice = _load(lang, selected)
    text = unicodedata.normalize("NFC", text)
    if lang == "ro":
        text = prepare_romanian(text)
    buf = io.BytesIO()
    lead_samples = round(voice.config.sample_rate * SPEECH_LEAD_MS / 1000)
    timeline = [{"v": "REST", "t": 0, "d": SPEECH_LEAD_MS}]
    offset, aligned = lead_samples, True
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(voice.config.sample_rate)
        # Keep the consonant intact: add silence instead of fading or trimming it.
        # The same offset is applied to every sample-aligned viseme below.
        wf.writeframes(b'\x00\x00' * lead_samples)
        pieces = short_pieces(text) if lang == "ro" and not (selected or "").startswith("liana") else [text]
        for index, piece in enumerate(pieces):
            if index:
                gap = round(voice.config.sample_rate * .07)
                start = round(offset * 1000 / voice.config.sample_rate)
                wf.writeframes(b'\x00\x00' * gap)
                offset += gap
                timeline.append({"v":"REST", "t":start, "d":round(offset*1000/voice.config.sample_rate)-start})
            for chunk in voice.synthesize(piece, include_alignments=True):
                wf.writeframes(chunk.audio_int16_bytes)
                entries = chunk_timeline(chunk, offset)
                if entries is None:
                    aligned = False
                else:
                    timeline.extend(entries)
                offset += len(chunk.audio_float_array)
    return Speech(buf.getvalue(), timeline if aligned and timeline else None)


async def synthesize(text, lang, selected=None):
    return await asyncio.to_thread(_synth, text, lang, selected)


def speech_window_ms(wav_bytes, threshold=400):
    """(început, sfârșit) al vorbirii în ms, ignorând liniștea de la capete."""
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        rate, n = wf.getframerate(), wf.getnframes()
        samples = array("h")
        samples.frombytes(wf.readframes(n))
    first = next((i for i, s in enumerate(samples) if abs(s) > threshold), 0)
    last = next((i for i in range(len(samples) - 1, -1, -1) if abs(samples[i]) > threshold),
                len(samples) - 1)
    return first / rate * 1000, (last + 1) / rate * 1000
