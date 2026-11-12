"""Real VIVERSE VRM, facial geometry, audio clock and avatar switching checks."""
import json
import base64
import io
import wave
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler, audio

ROOT = Path(__file__).resolve().parents[2]

def longer_audio():
    with wave.open(io.BytesIO(base64.b64decode(audio()))) as source:
        params, frames = source.getparams(), source.readframes(source.getnframes())
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as target:
        target.setparams(params)
        target.writeframes(frames * 3)
    return base64.b64encode(buffer.getvalue()).decode()

def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'frontend')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--autoplay-policy=no-user-gesture-required'])
            page = browser.new_page(viewport={'width':1280, 'height':800})
            errors, sockets, messages = [], [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            page.route('**/favicon.ico', lambda r: r.fulfill(status=204))
            page.route('**/api/config', lambda r: r.fulfill(json={'model':'gemma3:4b'}))
            def connected(ws):
                sockets.append(ws)
                ws.on_message(lambda data: messages.append(json.loads(data)))
            page.route_web_socket('**/ws', connected)
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_function("document.querySelector('#view').dataset.avatar === 'character'", timeout=30000)
            assert page.locator('.appearance').is_hidden()
            artifacts = ROOT / 'artifacts'
            artifacts.mkdir(exist_ok=True)
            page.wait_for_timeout(350)
            page.screenshot(path=str(artifacts / 'viverse.png'))
            print('PASS: real VRM loads, avatar selected and portrait rendered', flush=True)
            metrics = page.evaluate('''async () => {
              const {CharacterAvatar, activeViseme, activeSpeechPose} = await import('./character.js');
              const avatar = new CharacterAvatar(); await avatar.load();
              const THREE = await import('three');
              avatar.root.updateMatrixWorld(true);
              const headY = avatar.bones.head.getWorldPosition(new THREE.Vector3()).y;
              const relaxed = ['leftHand','rightHand'].every(name =>
                avatar.bones[name].getWorldPosition(new THREE.Vector3()).y < headY - .3);
              const mesh = avatar.meshes.find(m => 'jawOpen' in m.morphTargetDictionary);
              const weight = name => mesh.morphTargetInfluences[mesh.morphTargetDictionary[name]];
              const groups = {};
              for(const [group,shape] of Object.entries({A:'jawOpen', O:'mouthFunnel', E:'mouthStretchLeft',
                I:'mouthStretchLeft', U:'mouthPucker', SCHWA:'jawOpen', SHCH:'mouthFunnel', TH:'tongueOut',
                A_O:'jawOpen', E_I:'mouthStretchLeft', BMP:'mouthClose',
                FV:'mouthShrugLower', W_OO:'mouthPucker', LDTNS:'jawOpen'})) {
                for(let i=0;i<60;i++) avatar.update(1/60,1,'speaking',.08,group);
                groups[group]=weight(shape);
              }
              for(let i=0;i<60;i++) avatar.update(1/60,1,'idle',0,'REST');
              const rest = ['jawOpen','mouthPucker','mouthClose'].map(weight);
              const fps = [];
              for(const rate of [30,120]) {
                avatar.current = {}; avatar.setMorph('jawOpen',0);
                for(let i=0;i<rate;i++) avatar.update(1/rate,1,'speaking',.08,'A_O');
                fps.push(weight('jawOpen'));
              }
              const shape = mesh.geometry.morphAttributes.position[mesh.morphTargetDictionary.jawOpen];
              let deformation = 0;
              for(let i=0;i<shape.count;i++) deformation=Math.max(deformation,Math.abs(shape.getY(i)));
              const clips=[{start:10,end:11,visemes:[{v:'A_O',t:100,d:300},{v:'BMP',t:400,d:200}]}];
              avatar.update(1/60,3,'idle',0,'REST');
              avatar.update(1/60,3.09,'idle',0,'REST');
              const blink=weight('eyeBlinkLeft');
              const blend = activeSpeechPose(clips,10.395);
              const pause = activeSpeechPose([{start:0,end:1,visemes:[{v:'REST',t:0,d:500},{v:'A',t:500,d:500}]}],.49);
              avatar.setLook(.8,.4,true);
              for(let i=0;i<60;i++) avatar.update(1/60,4,'idle',0,'REST');
              const gaze = avatar.bones.leftEye.quaternion.angleTo(avatar.rest.leftEye);
              const headTurn = avatar.bones.head.quaternion.angleTo(avatar.rest.head);
              const rightLook = avatar.bones.leftEye.quaternion.clone();
              avatar.setLook(-.8,.4,true);
              for(let i=0;i<60;i++) avatar.update(1/60,4,'idle',0,'REST');
              const gazeRange = rightLook.angleTo(avatar.bones.leftEye.quaternion);
              const eyeIndex = mesh.skeleton.bones.indexOf(avatar.bones.leftEye);
              const joints = mesh.geometry.attributes.skinIndex, weights = mesh.geometry.attributes.skinWeight;
              let eyeVertices = 0;
              for(let i=0;i<joints.count;i++) for(let k=0;k<4;k++) {
                if(joints.array[i*4+k] === eyeIndex && weights.array[i*4+k] > .5) eyeVertices++;
              }
              avatar.beginPhrase('Pot să îți explic.',5);
              for(let i=0;i<84;i++) avatar.update(1/60,5+i/60,'speaking',.08,'A');
              const elbow = Math.max(...['leftLowerArm','rightLowerArm'].map(name =>
                avatar.bones[name].quaternion.angleTo(avatar.rest[name])));
              avatar.root.updateMatrixWorld(true);
              const handsBelowNeck = ['leftHand','rightHand'].every(name =>
                avatar.bones[name].getWorldPosition(new THREE.Vector3()).y <
                avatar.bones.neck.getWorldPosition(new THREE.Vector3()).y - .1);
              for(let i=0;i<120;i++) avatar.update(1/60,7+i/60,'idle',0,'REST');
              const relaxedAgain = ['leftUpperArm','rightUpperArm','leftLowerArm','rightLowerArm'].every(name =>
                avatar.bones[name].quaternion.angleTo(avatar.rest[name]) < .001);
              avatar.setLook(0,0,false);
              avatar.root.updateMatrixWorld(true);
              const foot=avatar.root.getObjectByName('Avatar_LeftFoot');
              const footBefore=foot.getWorldPosition(new THREE.Vector3());
              const positions=new THREE.Box3(); let spineMotion=0;
              const initialSpine=avatar.bones.spine.quaternion.clone();
              for(let i=0;i<720;i++) {
                avatar.update(1/60,10+i/60,'idle',0,'REST');
                avatar.root.updateMatrixWorld(true);
                positions.expandByPoint(avatar.bones.head.getWorldPosition(new THREE.Vector3()));
                spineMotion=Math.max(spineMotion,initialSpine.angleTo(avatar.bones.spine.quaternion));
              }
              const idleTravel=positions.getSize(new THREE.Vector3()).length();
              const footDrift=footBefore.distanceTo(foot.getWorldPosition(new THREE.Vector3()));
              return {groups,rest,fps,deformation,blink,relaxed,blend,pause,gaze,headTurn,gazeRange,eyeVertices,elbow,handsBelowNeck,relaxedAgain,idleTravel,footDrift,spineMotion,
                morphs:Object.keys(mesh.morphTargetDictionary).length, bones:Object.keys(avatar.bones),
                timeline:[9,10.05,10.2,10.5,10.8,12].map(t=>activeViseme(clips,t)),
                fallback:activeViseme([{start:0,end:1,visemes:[]}],.5)};
            }''')
            assert metrics['morphs'] == 60, metrics
            assert metrics['blend']['mix'] > 0 and metrics['pause']['mix'] == 0, metrics
            assert metrics['relaxed'], metrics
            assert all(v > .05 for v in metrics['groups'].values()), metrics
            assert all(v < .001 for v in metrics['rest']), metrics
            assert abs(metrics['fps'][0]-metrics['fps'][1]) < .0001, metrics
            assert metrics['deformation'] > .001 and metrics['blink'] > .9 and metrics['gaze'] > .1, metrics
            assert metrics['gaze'] > metrics['headTurn'] * 4 and metrics['gazeRange'] > .35, metrics
            assert metrics['eyeVertices'] > 100, metrics
            assert metrics['elbow'] < .001 and metrics['relaxedAgain'], metrics
            assert metrics['handsBelowNeck'], metrics
            assert .003 < metrics['idleTravel'] < .15 and .002 < metrics['spineMotion'] < .15, metrics
            assert metrics['footDrift'] < .000001, metrics
            assert metrics['timeline'] == ['REST','REST','A_O','BMP','REST','REST'], metrics
            assert metrics['fallback'] is None, metrics
            assert all(b in metrics['bones'] for b in ['head','neck','leftEye','rightEye']), metrics
            print('PASS: facial animation, idle posture and breathing with anchored feet, lowered arms, gaze and 30/120 FPS lerp', flush=True)
            assert page.locator('#avatar-mode option:checked').inner_text() == 'Personaj 3D'
            page.mouse.move(820,180)
            page.wait_for_timeout(700)
            page.screenshot(path=str(artifacts / 'character-gaze.png'))
            assert page.locator('#speaker, #voice').count() == 0
            page.locator('#msg').fill('Test avatar')
            page.locator('#msg').press('Enter')
            page.wait_for_function("document.querySelector('#view').dataset.state === 'thinking'")
            turn = messages[-1]['id']
            assert messages[-1]['voice'] == 'raluca'
            sockets[-1].send(json.dumps({'type':'speech','turn':turn,'audio':longer_audio(),'text':'Bună! Îți explic imediat.',
                'visemes':[{'v':'A_O','t':0,'d':3000}]}))
            sockets[-1].send(json.dumps({'type':'done','turn':turn}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'speaking'")
            page.wait_for_timeout(1150)
            page.screenshot(path=str(artifacts / 'viverse-speaking.png'))
            page.locator('#avatar-mode').select_option('particles')
            page.wait_for_function("document.querySelector('#view').dataset.avatar === 'particles'")
            assert page.locator('.appearance').is_visible()
            page.locator('#avatar-mode').select_option('character')
            page.wait_for_function("document.querySelector('#view').dataset.avatar === 'character'")
            assert page.locator('#view').get_attribute('data-state') == 'speaking'
            page.locator('#stop').click()
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            page.reload()
            page.wait_for_function("document.querySelector('#view').dataset.avatar === 'character'")
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_timeout(300)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(artifacts / 'viverse-mobile.png'))
            assert not errors, errors
            print('PASS: switching during speech, Stop, saved choice, mobile and shaders', flush=True)
            failed = browser.new_page()
            failed.route('**/assets/*.vrm', lambda r:r.fulfill(status=404,body='missing'))
            failed.route('**/api/config',lambda r:r.fulfill(json={'model':'gemma3:4b'}))
            failed.route_web_socket('**/ws',lambda ws:None)
            failed.goto(f'http://127.0.0.1:{server.server_port}')
            failed.wait_for_function("document.querySelector('#avatar-load').textContent.includes('Nu pot încărca')")
            assert failed.locator('#view').get_attribute('data-avatar') == 'particles'
            assert failed.locator('#avatar-mode').input_value() == 'particles'
            print('PASS: missing VRM leaves particles available',flush=True)
            browser.close()
    finally:
        server.shutdown(); server.server_close()

if __name__ == '__main__':
    run()
