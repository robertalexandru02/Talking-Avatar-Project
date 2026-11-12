"""Local Romanian/English microphone transcription. Audio stays in memory."""
import io
import os
import threading
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "models" / "whisper-small"
MAX_SECONDS = 60
_model = None
_lock = threading.Lock()

def transcribe(data, lang):
    global _model
    if lang not in ("ro", "en"):
        raise ValueError("Limba trebuie să fie ro sau en.")
    from faster_whisper import WhisperModel, decode_audio
    audio = decode_audio(io.BytesIO(data), sampling_rate=16000)
    if len(audio) > 16000 * MAX_SECONDS:
        raise ValueError("Înregistrarea poate avea maximum 60 de secunde.")
    if len(audio) < 1600:
        return ""
    import numpy as np
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio * audio)))
    if peak < .001 or rms < .00008:
        return ""
    # Boost quiet but non-silent captures before VAD. Bound the gain to avoid
    # turning almost-silent input into artificial speech-like noise.
    if peak < .15:
        audio = audio * min(8.0, .4 / max(peak, .0001))
    with _lock:
        if _model is None:
            if not (MODEL_DIR / "model.bin").is_file():
                raise RuntimeError("Lipsește modelul microfonului. Rulează python download_asr.py în backend.")
            _model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8",
                                  cpu_threads=min(6, os.cpu_count() or 4), local_files_only=True)
        segments, _ = _model.transcribe(audio, language=lang, beam_size=3,
            vad_filter=True, condition_on_previous_text=False,
            vad_parameters={"min_silence_duration_ms":350})
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            # A quiet short utterance can be discarded entirely by the VAD.
            # Retry using Whisper's own speech probability and log-probability.
            segments, _ = _model.transcribe(audio, language=lang, beam_size=3,
                vad_filter=False, condition_on_previous_text=False, no_speech_threshold=.5)
            text = " ".join(segment.text.strip() for segment in segments
                            if segment.no_speech_prob < .6 and segment.avg_logprob > -1.05).strip()
        return text
