"""Real Chromium MediaRecorder -> live local API, with a WAV as microphone input."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def run():
    source=ROOT/'artifacts/voice-raluca.wav'
    if not source.is_file():raise RuntimeError('Run tests/smoke/voice_smoke.py first.')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--use-fake-device-for-media-stream',
            '--use-fake-ui-for-media-stream',f'--use-file-for-fake-audio-capture={source}',
            '--autoplay-policy=no-user-gesture-required'])
        page=browser.new_page(permissions=['microphone'],viewport={'width':1280,'height':850})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_init_script("localStorage.setItem('avatar-mode','particles')")
        page.goto('http://127.0.0.1:8000')
        page.wait_for_function("!document.querySelector('#msg').disabled")
        page.locator('#microphone').click()
        page.wait_for_function("document.querySelector('#microphone').dataset.state==='recording'")
        page.wait_for_function("document.querySelector('#microphone-level').value > .01",timeout=10000)
        assert page.locator('#microphone-tools').is_visible()
        page.wait_for_timeout(5000)
        print('Recording state:',page.locator('#microphone-status').inner_text().encode('ascii','backslashreplace').decode(),flush=True)
        page.locator('#microphone').click()
        page.wait_for_function("document.querySelector('#microphone').dataset.state==='idle'",timeout=60000)
        result=page.locator('#msg').input_value()
        print('Transcript:',result.encode('ascii','backslashreplace').decode(),flush=True)
        print('Toast:',page.locator('#toast').inner_text().encode('ascii','backslashreplace').decode(),flush=True)
        print('Errors:',errors,flush=True)
        assert result and not errors
        browser.close()

if __name__=='__main__':run()
