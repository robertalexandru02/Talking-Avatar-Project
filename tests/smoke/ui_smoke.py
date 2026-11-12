"""Studio UI: suggestions, keyboard, export, new session and responsive layout."""
import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]

def run():
    (ROOT/'artifacts').mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'frontend')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width':1440,'height':960},accept_downloads=True)
            page.add_init_script("localStorage.setItem('avatar-mode','particles')")
            errors, messages, sockets = [], [], []
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/favicon.ico',lambda r:r.fulfill(status=204))
            page.route('**/api/config',lambda r:r.fulfill(json={'model':'gemma3:4b'}))
            def connected(ws):
                sockets.append(ws)
                ws.on_message(lambda data:messages.append(json.loads(data)))
            page.route_web_socket('**/ws',connected)
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_function("!document.querySelector('#msg').disabled")
            assert page.locator('#empty-state').is_visible()
            assert page.locator('#send').is_disabled()
            assert page.locator('#view-title').inner_text() == 'Roi de particule'
            assert page.locator('#voice-label').inner_text() == 'Liana · voce robotică'
            page.set_viewport_size({'width':1280,'height':800})
            page.wait_for_timeout(150)
            suggestions=page.locator('[data-prompt]').last.bounding_box()
            toolbar=page.locator('.composer-toolbar').bounding_box()
            assert suggestions['y'] + suggestions['height'] <= toolbar['y'] + 2
            page.screenshot(path=str(ROOT/'artifacts/studio-empty.png'))
            page.set_viewport_size({'width':1440,'height':960})
            page.locator('[data-prompt]').first.click()
            assert 'model lingvistic' in page.locator('#msg').input_value()
            assert not messages
            page.locator('#msg').fill('Salut')
            page.locator('#msg').press('Shift+Enter')
            page.locator('#msg').type('O întrebare.')
            assert '\n' in page.locator('#msg').input_value()
            page.locator('#msg').press('Enter')
            page.wait_for_function("document.querySelector('#message-count').textContent === '1'")
            for _ in range(50):
                if messages: break
                page.wait_for_timeout(20)
            assert '\n' in messages[-1]['text']
            assert page.locator('#empty-state').is_hidden()
            turn=messages[-1]['id']
            sockets[-1].send(json.dumps({'type':'token','turn':turn,'text':'Bună! Cu ce te pot ajuta?'}))
            sockets[-1].send(json.dumps({'type':'done','turn':turn}))
            page.wait_for_function("document.querySelector('.bot').textContent.includes('Cu ce')")
            with page.expect_download() as download_info:
                page.locator('#export-chat').click()
            download=download_info.value
            contents=Path(download.path()).read_text(encoding='utf-8')
            assert 'TU\nSalut' in contents and 'ASISTENT\nBună!' in contents
            page.locator('#reset-camera').click()
            assert page.locator('#toast').inner_text().startswith('Camera')
            if page.evaluate('document.fullscreenEnabled'):
                page.locator('#fullscreen').click()
                page.wait_for_function('!!document.fullscreenElement')
                page.locator('#fullscreen').click()
                page.wait_for_function('!document.fullscreenElement')
            page.wait_for_timeout(600)
            artifacts=ROOT/'artifacts'; artifacts.mkdir(exist_ok=True)
            page.screenshot(path=str(artifacts/'studio-conversation.png'))
            old_turn=turn
            page.locator('#new-chat').click()
            page.wait_for_function("!document.querySelector('#msg').disabled")
            assert len(sockets) == 2 and page.locator('#log').inner_text() == ''
            assert page.locator('#message-count').inner_text() == '0'
            assert page.locator('#empty-state').is_visible()
            assert page.locator('#export-chat').is_disabled()
            page.locator('#msg').fill('O conversație nouă')
            previous_messages=len(messages)
            page.locator('#msg').press('Enter')
            page.wait_for_function("document.querySelector('#message-count').textContent === '1'")
            for _ in range(50):
                if len(messages)>previous_messages: break
                page.wait_for_timeout(20)
            assert messages[-1]['id'] != old_turn
            page.locator('#stop').click()
            for width,height in [(1280,800),(1024,768),(768,1024),(390,844),(360,740)]:
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(120)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width,height)
                page.locator('#msg').scroll_into_view_if_needed()
                assert page.locator('#msg').is_visible()
            page.screenshot(path=str(artifacts/'studio-mobile-chat.png'))
            assert not errors,errors
            print('PASS: suggestions, multiline/Enter, count, TXT export, new session, camera reset/fullscreen and five responsive sizes',flush=True)
            browser.close()
    finally:
        server.shutdown(); server.server_close()

if __name__ == '__main__':
    run()
