"""Microphone lifecycle, review-before-send, replay, copy, samples and project page."""
import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler, audio

ROOT=Path(__file__).resolve().parents[2]
MOCK_MIC = '''
window.micTest={deny:false,stopped:0,delay:false,copied:''};
Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.micTest.copied=text}}});
navigator.mediaDevices.getUserMedia=async()=>{
 if(window.micTest.deny)throw new DOMException('Denied','NotAllowedError');
 return {getTracks:()=>[{stop:()=>window.micTest.stopped++}]};
};
window.MediaRecorder=class {
 static isTypeSupported(){return true}
 constructor(){this.state='inactive';this.mimeType='audio/webm'}
 start(){this.state='recording'}
 stop(){this.state='inactive';queueMicrotask(()=>{
  this.ondataavailable?.({data:new Blob(['test-audio'])});this.onstop?.();
 })}
};
const originalFetch=window.fetch;
window.fetch=(url,options)=>String(url).includes('/api/transcribe')&&window.micTest.delay
 ?new Promise(resolve=>setTimeout(()=>resolve(new Response(JSON.stringify({text:'Text întârziat'}),{status:200,headers:{'Content-Type':'application/json'}})),700))
 :originalFetch(url,options);
'''

def run():
    (ROOT/'artifacts').mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'frontend')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
            page=browser.new_page(viewport={'width':1280,'height':850})
            page.add_init_script(MOCK_MIC)
            page.add_init_script("localStorage.setItem('avatar-mode','particles')")
            errors,messages,sockets=[],[],[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/favicon.ico',lambda r:r.fulfill(status=204))
            page.route('**/api/config',lambda r:r.fulfill(json={'model':'gemma3:4b'}))
            page.route('**/api/transcribe?*',lambda r:r.fulfill(json={'text':'Bună, aceasta este o întrebare.'}))
            page.route('**/api/speech-sample',lambda r:r.fulfill(json={'audio':audio(),'text':'Mama pune pâinea pe masă.',
                'visemes':[{'v':'BMP','t':0,'d':200},{'v':'A','t':200,'d':1000}],'alignment':'piper'}))
            def connected(ws):
                sockets.append(ws);ws.on_message(lambda data:messages.append(json.loads(data)))
            page.route_web_socket('**/ws',connected)
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_function("!document.querySelector('#msg').disabled")
            page.locator('#msg').fill('Salut');page.locator('#msg').press('Enter')
            for _ in range(100):
                if any(m['type']=='chat' for m in messages):break
                page.wait_for_timeout(20)
            turn=next(m['id'] for m in messages if m['type']=='chat')
            sockets[-1].send(json.dumps({'type':'token','turn':turn,'text':'Bună! Cu ce te pot ajuta?'}))
            sockets[-1].send(json.dumps({'type':'speech','turn':turn,'audio':audio(),'visemes':[{'v':'A','t':0,'d':1200}]}))
            sockets[-1].send(json.dumps({'type':'done','turn':turn}))
            page.wait_for_function("document.querySelector('#view').dataset.state==='speaking'")
            page.wait_for_function("document.querySelector('.response-timing').textContent.includes('Voce')")
            page.get_by_role('button',name='Copiază răspunsul').click()
            assert page.evaluate('window.micTest.copied')=='Bună! Cu ce te pot ajuta?'
            page.locator('#msg').fill('Notă')
            page.locator('#microphone').click()
            page.wait_for_function("document.querySelector('#microphone').dataset.state==='recording'")
            page.wait_for_function("document.querySelector('#view').dataset.state==='idle'")
            page.locator('#microphone').click()
            page.wait_for_function("document.querySelector('#msg').value.includes('aceasta')")
            assert page.locator('#msg').input_value().startswith('Notă\n')
            assert len([m for m in messages if m['type']=='chat'])==1
            assert page.evaluate('window.micTest.stopped')>0
            page.get_by_role('button',name='Reascultă răspunsul').click()
            page.wait_for_function("document.querySelector('#view').dataset.state==='speaking'")
            assert len([m for m in messages if m['type']=='chat'])==1
            page.locator('#stop').click()
            page.wait_for_function("document.querySelector('#view').dataset.state==='idle'")
            page.evaluate('window.micTest.deny=true')
            page.locator('#microphone').click()
            page.wait_for_function("document.querySelector('#toast').textContent.includes('refuzat')")
            assert page.locator('#microphone').get_attribute('data-state')=='idle'
            page.evaluate('window.micTest.deny=false;window.micTest.delay=true')
            before=page.locator('#msg').input_value()
            page.locator('#microphone').click()
            page.wait_for_function("document.querySelector('#microphone').dataset.state==='recording'")
            page.locator('#microphone').click()
            page.wait_for_function("document.querySelector('#microphone').dataset.state==='transcribing'")
            page.locator('#microphone').click();page.wait_for_timeout(800)
            assert page.locator('#msg').input_value()==before
            page.locator('#speech-check').click()
            assert page.locator('#articulation-dialog').is_visible()
            page.locator('[data-speech-sample="lips"]').click()
            page.wait_for_function("document.querySelector('#view').dataset.state==='speaking'")
            assert len([m for m in messages if m['type']=='chat'])==1
            page.locator('#stop').click()
            page.locator('#speech-check').click()
            with page.expect_request('**/api/speech-sample') as requested:
                page.locator('[data-speech-sample="technical"]').click()
            assert requested.value.post_data_json['sample']=='technical'
            page.wait_for_function("document.querySelector('#view').dataset.state==='speaking'")
            assert len([m for m in messages if m['type']=='chat'])==1
            page.locator('#stop').click()
            with page.expect_popup() as opened:
                page.get_by_role('link',name='Despre proiect — deschide într-o filă nouă').click()
            project=opened.value;project.wait_for_load_state();project.bring_to_front()
            assert project.locator('table tbody tr').count()==7
            project.locator('[data-viseme="A"]').click();project.wait_for_timeout(500)
            assert float(project.locator('#jaw-weight').evaluate('el=>el.value'))>.8
            project.locator('#run-demo').click()
            project.wait_for_function("document.querySelectorAll('.pipeline .active').length===1")
            assert project.locator('.pipeline .active').count()==1
            project.screenshot(path=str(ROOT/'artifacts/project-page.png'),full_page=True)
            project.set_viewport_size({'width':390,'height':844})
            assert project.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors,errors
            print('PASS: microphone interrupts, review before send, draft preserved, denial, stale transcription cancellation, copy, replay, timings, articulation samples and project demo',flush=True)
            browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':run()
