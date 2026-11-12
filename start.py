"""Prepare the local environment and start the laboratory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent
ENV = ROOT / 'backend' / '.venv'
REQUIREMENTS = ROOT / 'backend' / 'requirements.txt'
URL = 'http://localhost:8000'


def run(command):
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True)


def prepare_environment():
    python = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        print('Creez mediul Python...', flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV)
    fingerprint = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    stamp = ENV / '.requirements.sha256'
    if not stamp.is_file() or stamp.read_text() != fingerprint:
        print('Instalez dependentele. Prima instalare poate dura cateva minute.', flush=True)
        run([python, '-m', 'pip', 'install', '-r', REQUIREMENTS])
        stamp.write_text(fingerprint)
    return python


def get_json(url):
    with urlopen(url, timeout=3) as response:
        return json.load(response)


def is_laboratory_running():
    try:
        config = get_json(URL + '/api/config')
        return config.get('llm') == 'ollama' and config.get('tts') == 'piper'
    except (OSError, ValueError):
        return False


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def connect_ollama(url):
    try:
        return get_json(url + '/api/tags'), None
    except (OSError, ValueError):
        pass
    if url.rstrip('/') not in ('http://localhost:11434', 'http://127.0.0.1:11434'):
        raise RuntimeError('Nu pot contacta OLLAMA_URL. Verifica adresa din backend/.env.')
    executable = shutil.which('ollama')
    if not executable and os.name == 'nt':
        candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise RuntimeError('Instaleaza Ollama de la https://ollama.com/ si porneste din nou laboratorul.')
    print('Pornesc Ollama...', flush=True)
    logs = ROOT / 'artifacts'
    logs.mkdir(exist_ok=True)
    with (logs / 'ollama.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen([executable, 'serve'], stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        for _ in range(30):
            try:
                return get_json(url + '/api/tags'), process
            except (OSError, ValueError):
                if process.poll() is not None:
                    break
                time.sleep(1)
        raise RuntimeError('Ollama nu a pornit. Verifica artifacts/ollama.log.')
    except BaseException:
        stop_process(process)
        raise


def prepare_models(url, model, installed):
    names = {item.get('name') for item in installed.get('models', [])}
    if model not in names and model + ':latest' not in names:
        print('Descarc modelul ' + model + '. Pastreaza conexiunea la internet.', flush=True)
        request = Request(url + '/api/pull', data=json.dumps({'model':model}).encode(),
            headers={'Content-Type':'application/json'})
        previous = None
        complete = False
        with urlopen(request, timeout=180) as response:
            for line in response:
                event = json.loads(line)
                if event.get('error'):
                    raise RuntimeError('Ollama: ' + str(event['error']))
                status = event.get('status', '')
                if event.get('total'):
                    status += ' %d%%' % (int(event.get('completed', 0) / event['total'] * 10) * 10)
                if status != previous:
                    print(status, flush=True)
                    previous = status
                complete = event.get('status') == 'success'
        if not complete:
            raise RuntimeError('Descarcarea modelului a fost intrerupta. Porneste din nou launcherul.')
    run([sys.executable, '-B', ROOT / 'backend/download_voices.py'])
    whisper = ROOT / 'backend/models/whisper-small'
    required = ('config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt')
    if not all((whisper / name).is_file() and (whisper / name).stat().st_size for name in required):
        print('Descarc modelul pentru microfon...', flush=True)
        run([sys.executable, '-B', ROOT / 'backend/download_asr.py'])


def open_when_ready():
    for _ in range(120):
        if is_laboratory_running():
            webbrowser.open(URL)
            return
        time.sleep(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Instalare si pornire Talking Avatar')
    parser.add_argument('--setup-only', action='store_true', help='Pregateste modelele fara a porni laboratorul')
    parser.add_argument('--no-browser', action='store_true', help='Nu deschide automat browserul')
    args = parser.parse_args(argv)
    if not (3, 10) <= sys.version_info[:2] <= (3, 12):
        raise RuntimeError('Este necesar Python 3.10, 3.11 sau 3.12: https://www.python.org/downloads/')
    python = prepare_environment()
    if Path(sys.prefix).resolve() != ENV.resolve():
        return subprocess.call([str(python), '-B', str(ROOT / 'start.py'), *(argv if argv is not None else sys.argv[1:])], cwd=ROOT)
    if not args.setup_only and is_laboratory_running():
        print('Laboratorul ruleaza deja: ' + URL, flush=True)
        if not args.no_browser:
            webbrowser.open(URL)
        return 0
    sys.path.insert(0, str(ROOT / 'backend'))
    import config  # Load the existing optional .env; never overwrite it.
    url = os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    installed, owned_ollama = connect_ollama(url)
    try:
        prepare_models(url, os.getenv('OLLAMA_MODEL', 'gemma3:4b'), installed)
        if args.setup_only:
            print('Instalarea este pregatita.', flush=True)
            return 0
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', 8000))
            except OSError as error:
                raise RuntimeError('Portul 8000 este ocupat de alta aplicatie.') from error
        if not args.no_browser:
            threading.Thread(target=open_when_ready, daemon=True).start()
        print('Laborator: ' + URL + ' | Ctrl+C pentru oprire.', flush=True)
        import uvicorn
        uvicorn.run('main:app', host='127.0.0.1', port=8000)
        return 0
    finally:
        stop_process(owned_ollama)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nLaborator oprit.')
        sys.exit(0)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('\nEroare: ' + str(error), file=sys.stderr)
        sys.exit(1)
