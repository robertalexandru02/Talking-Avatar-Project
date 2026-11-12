"""Download Whisper small over HTTP with visible progress and resumable caching."""
import os
from pathlib import Path
import sys


def download(folder=None):
    # These settings must precede the first huggingface_hub import in this process.
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '60')
    from huggingface_hub import snapshot_download
    folder = Path(folder) if folder is not None else Path(__file__).parent / 'models/whisper-small'
    folder.mkdir(parents=True, exist_ok=True)
    print('Whisper small: descarcare HTTP (~484 MB). Nu este necesar un token.', flush=True)
    snapshot_download(
        repo_id='Systran/faster-whisper-small',
        local_dir=str(folder),
        allow_patterns=['config.json', 'preprocessor_config.json', 'model.bin',
                        'tokenizer.json', 'vocabulary.*'],
        max_workers=1,
    )
    for name in ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']:
        path = folder / name
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError('Lipseste fisierul ' + name)
    print('Modelul pentru microfon este pregatit.', flush=True)

if __name__ == "__main__":
    try:
        download()
    except KeyboardInterrupt:
        print('\nDescarcare intrerupta. Ruleaza din nou start.bat pentru reluare.', flush=True)
        sys.exit(1)
    except Exception as error:
        response = getattr(error, 'response', None)
        status = getattr(response, 'status_code', None)
        print(f'\nDescarcarea nu s-a terminat: {type(error).__name__}' +
              (f' (HTTP {status})' if status else '') +
              '. Verifica reteaua si ruleaza din nou start.bat.', file=sys.stderr)
        sys.exit(1)
