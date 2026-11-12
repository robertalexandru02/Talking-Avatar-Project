"""Descarcă vocile Piper (română + engleză) în backend/voices/."""
from pathlib import Path

import httpx

VOICES = {
    "ro_RO-raluca-high": (
        "https://huggingface.co/eduardem/piper-tts-romanian/resolve/main/voices/raluca"
    ),
    "ro_RO-sanda-medium": (
        "https://huggingface.co/eduardem/piper-tts-romanian/resolve/main/voices/sanda"
    ),
    "ro_RO-liana-medium": (
        "https://huggingface.co/eduardem/piper-liana-romanian/resolve/main/voices/liana-medium"
    ),
    "ro_RO-liana-high": (
        "https://huggingface.co/eduardem/piper-liana-romanian/resolve/main/voices/liana-high"
    ),
    "en_US-lessac-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
    ),
}

out = Path(__file__).parent / "voices"
out.mkdir(exist_ok=True)

for name, url in VOICES.items():
    for ext in (".onnx", ".onnx.json"):
        dest = out / f"{name}{ext}"
        if dest.exists() and dest.stat().st_size:
            continue
        print("descarc", dest.name)
        partial = dest.with_suffix(dest.suffix + ".part")
        with httpx.stream("GET", f"{url}/{name}{ext}", follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            with open(partial, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        partial.replace(dest)
print("gata")
