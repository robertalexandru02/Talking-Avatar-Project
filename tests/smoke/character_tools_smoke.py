"""Real material changes, scene presets, skeleton, wireframe and manual morph controls."""
import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler,audio

ROOT=Path(__file__).resolve().parents[2]

def run():
 (ROOT/'artifacts').mkdir(exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'frontend')))
 threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
   page=browser.new_page(viewport={'width':1440,'height':960});errors=[];sockets=[];messages=[]
   page.on('pageerror',lambda error:errors.append(str(error)))
   page.route('**/favicon.ico',lambda r:r.fulfill(status=204))
   page.route('**/api/config',lambda r:r.fulfill(json={'model':'gemma3:4b'}))
   def connected(ws):sockets.append(ws);ws.on_message(lambda text:messages.append(json.loads(text)))
   page.route_web_socket('**/ws',connected)
   page.goto(f'http://127.0.0.1:{server.server_port}')
   page.wait_for_function("document.querySelector('#view').dataset.avatar==='character'")
   metrics=page.evaluate('''async()=>{
    const {CharacterAvatar}=await import('./character.js');const THREE=await import('three');
    const a=new CharacterAvatar();await a.load();
    a.setAppearance({clothes:'#88aaff',hair:'#aa7799',glasses:false});
    const changed=[...a.materialBases].filter(([m])=>/Template|Hair/.test(m.name)).every(([m,b])=>!m.color.equals(b));
    const unchanged=[...a.materialBases].filter(([m])=>/Head|Body/.test(m.name)).every(([m,b])=>m.color.equals(b));
    const glasses=a.accessories.length>0&&a.accessories.every(m=>!m.visible);
    a.setInspection({skeleton:true,wireframe:true,manual:true,shape:'jawOpen',weight:.7});
    a.update(1/60,1,'idle',0,'REST');const manual=a.getMorph('jawOpen');
    const skeleton=a.skeletonHelper.visible&&a.skeletonHelper.geometry.attributes.position.count>0;
    const wire=[...a.materialBases.keys()].every(m=>m.wireframe);
    a.setInspection({shape:'mouthPucker',weight:.35});a.update(1/60,1,'idle',0,'REST');
    const clear=a.getMorph('jawOpen')===0&&Math.abs(a.getMorph('mouthPucker')-.35)<.00001;
    a.setInspection({manual:false,skeleton:false,wireframe:false});
    for(let i=0;i<60;i++)a.update(1/60,2,'speaking',.08,'A');
    const automatic=a.getMorph('jawOpen')>.3&&a.getMorph('mouthPucker')<.001;
    a.setAppearance({clothes:'#ffffff',hair:'#ffffff',glasses:true});
    const restored=[...a.materialBases].every(([m,b])=>m.color.equals(b))&&a.accessories.every(m=>m.visible);
    const camera=new THREE.PerspectiveCamera(32,1.2,.01,100);
    const controls={target:new THREE.Vector3(),update(){camera.lookAt(this.target)}};
    a.frameCamera(camera,controls);const portrait=camera.position.distanceTo(controls.target);
    a.setAppearance({framing:'full'});a.frameCamera(camera,controls);
    const full=camera.position.distanceTo(controls.target);camera.updateMatrixWorld(true);
    const visible=[a.bounds.min,a.bounds.max].map(v=>v.clone().project(camera)).every(v=>Math.abs(v.y)<1&&Math.abs(v.x)<1);
    const zoomChecks=[];
    for(const framing of ['portrait','full']) {
      a.setAppearance({framing});a.frameCamera(camera,controls);
      const original=camera.position.clone(),wide=controls.target.clone();
      const startDistance=camera.position.distanceTo(wide);
      const direction=camera.position.clone().sub(wide).normalize();
      camera.position.copy(wide).addScaledVector(direction,controls.minDistance);
      a.updateCameraFocus(camera,controls);controls.update();camera.updateMatrixWorld(true);
      const face=a.facePosition.clone().project(camera);
      const close=camera.position.clone();
      for(let i=0;i<20;i++)a.updateCameraFocus(camera,controls);
      const stable=close.distanceTo(camera.position)<.000001;
      camera.position.copy(controls.target).addScaledVector(direction,startDistance);
      a.updateCameraFocus(camera,controls);controls.update();
      zoomChecks.push(Math.abs(face.x)<.01&&Math.abs(face.y)<.01&&stable&&
        controls.target.distanceTo(wide)<.000001&&camera.position.distanceTo(original)<.000001);
    }
    return {changed,unchanged,glasses,manual,skeleton,wire,clear,automatic,restored,portrait,full,visible,zoom:zoomChecks.every(Boolean)};
   }''')
   assert all(metrics[k] for k in ['changed','unchanged','glasses','skeleton','wire','clear','automatic','restored','visible','zoom']),metrics
   assert abs(metrics['manual']-.7)<.00001 and metrics['full']>metrics['portrait']*2,metrics
   page.locator('#character-tools-button').click()
   page.locator('#character-theme').select_option('gallery')
   page.locator('#character-framing').select_option('full')
   page.locator('#character-glasses').uncheck()
   page.locator('#character-clothes').evaluate("el=>{el.value='#88aaff';el.dispatchEvent(new Event('input'))}")
   assert page.locator('#view').get_attribute('data-scene')=='gallery'
   page.wait_for_timeout(250);page.screenshot(path=str(ROOT/'artifacts/character-customized.png'))
   page.locator('#inspector-tab').click()
   assert '54' in page.locator('#character-model-info').inner_text()
   page.locator('#inspect-skeleton').check();page.locator('#inspect-wireframe').check();page.locator('#inspect-manual').check()
   page.locator('#inspect-weight').evaluate("el=>{el.value='.7';el.dispatchEvent(new Event('input'))}")
   page.wait_for_function("Math.abs(document.querySelector('[data-morph=jawOpen]').value-.7)<.001")
   page.screenshot(path=str(ROOT/'artifacts/character-laboratory.png'))
   page.locator('#close-character-tools').click()
   page.locator('#character-tools-button').click()
   assert not page.locator('#inspect-manual').is_checked()
   page.locator('#inspect-manual').check()
   page.locator('#msg').fill('Salut');page.locator('#msg').press('Enter')
   for _ in range(100):
    if any(m['type']=='chat' for m in messages):break
    page.wait_for_timeout(20)
   assert not page.locator('#inspect-manual').is_checked()
   turn=next(m['id'] for m in reversed(messages) if m['type']=='chat')
   sockets[-1].send(json.dumps({'type':'token','turn':turn,'text':'Bună!'}))
   sockets[-1].send(json.dumps({'type':'speech','turn':turn,'audio':audio(),'visemes':[{'v':'A','t':0,'d':1300}]}))
   sockets[-1].send(json.dumps({'type':'done','turn':turn}))
   page.wait_for_function("document.querySelector('#inspect-source').textContent.includes('A')&&document.querySelector('[data-morph=jawOpen]').value>.1")
   page.locator('#stop').click()
   page.reload();page.wait_for_function("document.querySelector('#view').dataset.avatar==='character'")
   page.locator('#character-tools-button').click()
   assert page.locator('#character-theme').input_value()=='gallery'
   assert page.locator('#character-framing').input_value()=='full'
   assert not page.locator('#character-glasses').is_checked()
   page.locator('#avatar-mode').select_option('particles')
   assert page.locator('#character-tools-button').is_hidden() and page.locator('#character-tools').is_hidden()
   page.locator('#avatar-mode').select_option('character')
   page.wait_for_function("document.querySelector('#view').dataset.avatar==='character'")
   page.set_viewport_size({'width':390,'height':844})
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   assert not errors,errors
   print('PASS: real material/accessory changes, scene themes, portrait/full frame, skeleton, wireframe, exact manual weights, speech restoration, persistence and mobile',flush=True)
   browser.close()
 finally:server.shutdown();server.server_close()

if __name__=='__main__':run()
