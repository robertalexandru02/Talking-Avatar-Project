"""Optional browser checks: pip install playwright; python -m playwright install chromium.

Run from the repository root, using PLAYWRIGHT_BROWSERS_PATH=.browser-cache if needed.
Uses a temporary local static server and deterministic WebSocket/audio fixtures.
"""
import base64
import io
import json
import math
import threading
import wave
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def audio():
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"".join(int(math.sin(i * 2 * math.pi * 220 / 22050) * 6000)
                               .to_bytes(2, "little", signed=True) for i in range(33075)))
    return base64.b64encode(out.getvalue()).decode()


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "frontend")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.add_init_script("localStorage.setItem('avatar-mode', 'particles');")
            errors, messages, connections = [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

            def connected(ws):
                connections.append(ws)
                ws.on_message(lambda text: messages.append(json.loads(text)))

            page.route_web_socket("**/ws", connected)
            page.route("**/favicon.ico", lambda route: route.fulfill(status=204))
            page.route("**/api/config", lambda route: route.fulfill(json={"llm": "ollama", "tts": "piper", "voice": "Liana"}))
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.wait_for_function("document.querySelector('#connection').textContent.startsWith('Conectat')")
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            dsp = page.evaluate("""async () => {
              const { VoiceEffect } = await import('./voice-effect.js');
              async function render(mode, silent = false) {
                const ctx = new OfflineAudioContext(1, 22050, 22050);
                const fx = new VoiceEffect(ctx, ctx.destination);
                fx.setMode(mode);
                const buffer = ctx.createBuffer(1, 22050, 22050);
                const data = buffer.getChannelData(0);
                if (!silent) for (let i = 0; i < data.length; i++) {
                  data[i] = Math.sin(i * 2 * Math.PI * 220 / 22050) * 0.25;
                }
                const src = ctx.createBufferSource();
                src.buffer = buffer;
                src.connect(fx.input);
                src.start();
                return (await ctx.startRendering()).getChannelData(0);
              }
              const robot = await render('robot');
              const natural = await render('natural');
              const silent = await render('robot', true);
              let difference = 0, peak = 0, silence = 0, originalError = 0;
              for (let i = 11025; i < robot.length; i++) {
                difference += Math.abs(robot[i] - natural[i]);
                peak = Math.max(peak, Math.abs(robot[i]));
                silence = Math.max(silence, Math.abs(silent[i]));
                originalError = Math.max(originalError,
                  Math.abs(natural[i] - Math.sin(i * 2 * Math.PI * 220 / 22050) * 0.25));
              }
              return { difference: difference / 11025, peak, silence, originalError };
            }""")
            assert dsp["difference"] > 0.01, dsp
            assert 0 < dsp["peak"] < 1, dsp
            assert dsp["silence"] == 0, dsp
            assert dsp["originalError"] < 0.001, dsp
            print("PASS: robotic effect changes audio, original mode bypasses it, silence stays silent")
            page.wait_for_timeout(600)
            artifacts = ROOT / "artifacts"
            artifacts.mkdir(exist_ok=True)
            page.screenshot(path=str(artifacts / "idle.png"))

            # Freeze orbit time, while allowing transitions to settle, so pixel
            # comparisons measure cursor repulsion rather than orbital motion.
            page.evaluate("""async () => {
              const THREE = await import('three');
              window.restoreDelta = THREE.Clock.prototype.getDelta;
              THREE.Clock.prototype.getDelta = function() {
                this.elapsedTime = 1;
                return 1 / 60;
              };
            }""")
            box = page.locator("#view canvas").bounding_box()
            hover_x, hover_y = box["x"] + box["width"] * .6, box["y"] + box["height"] * .5

            def light_near_cursor():
                return page.evaluate("""() => new Promise(resolve => requestAnimationFrame(() => {
                  const canvas = document.querySelector('#view canvas');
                  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
                  const pixels = new Uint8Array(32 * 32 * 4);
                  gl.readPixels(Math.floor(gl.drawingBufferWidth * .6) - 16,
                    Math.floor(gl.drawingBufferHeight * .5) - 16,
                    32, 32, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
                  let energy = 0;
                  for (let i = 0; i < pixels.length; i += 4) {
                    energy += Math.max(0, pixels[i] - 7)
                      + Math.max(0, pixels[i + 1] - 11) + Math.max(0, pixels[i + 2] - 22);
                  }
                  resolve(energy);
                }))""")

            page.mouse.move(1100, 100)
            page.wait_for_timeout(400)
            before = light_near_cursor()
            page.mouse.move(hover_x, hover_y)
            page.wait_for_timeout(600)
            hovered = light_near_cursor()
            page.screenshot(path=str(artifacts / "cursor-repulsion.png"))
            # The cursor deforms density but must not punch a completely empty hole.
            assert before > 1000 and hovered > before * .08, (before, hovered)
            assert abs(hovered - before) > before * .05, (before, hovered)
            page.mouse.move(1100, 100)
            page.wait_for_timeout(1500)
            released = light_near_cursor()
            assert abs(released - before) < before * .2, (before, released)
            page.evaluate("""async () => {
              const THREE = await import('three');
              THREE.Clock.prototype.getDelta = window.restoreDelta;
            }""")
            print("PASS: cursor deforms particles without an empty disk; particles return on leave")

            physics = page.evaluate("""async () => {
              const { ParticleSwarm } = await import('./particles.js');
              const THREE = await import('three');
              const camera = new THREE.PerspectiveCamera(45, 1, .1, 100);
              camera.position.set(0, 0, 6.5);
              function make() {
                const originalRandom = Math.random;
                let seed = 123456;
                Math.random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
                try { return new ParticleSwarm(1000); } finally { Math.random = originalRandom; }
              }
              const magnitude = array => Math.sqrt(array.reduce((s, x) => s + x * x, 0) / array.length);
              function simulate(fps) {
                const swarm = make();
                swarm.setPointer(.12, .05, true);
                for (let i = 0; i < fps; i++) swarm.update(1 / fps, 1, 'idle', 0, camera);
                const active = magnitude(swarm.offsets);
                const snapshot = Array.from(swarm.offsets);
                swarm.setPointer(.12, .05, false);
                swarm.update(1 / fps, 1, 'idle', 0, camera);
                const release = magnitude(swarm.offsets);
                for (let i = 0; i < fps * 3; i++) swarm.update(1 / fps, 1, 'idle', 0, camera);
                const settled = magnitude(swarm.offsets);
                const finite = [...swarm.positions, ...swarm.trailPositions].every(Number.isFinite);
                return { active, release, settled, snapshot, finite };
              }
              const a = simulate(30), b = simulate(120);
              const difference = Math.sqrt(a.snapshot.reduce((s, x, i) => s + (x - b.snapshot[i]) ** 2, 0) / a.snapshot.length);
              const speech = make();
              for (let i = 0; i < 180; i++) speech.update(1 / 60, 1, 'speaking', 0, camera);
              const radius = () => {
                let max = 0;
                for (let i = 0; i < speech.positions.length; i += 3) max = Math.max(max, Math.hypot(...speech.positions.subarray(i, i + 3)));
                return max;
              };
              const quietRadius = radius();
              const beforeGesture = Array.from(speech.positions);
              speech.beginPhrase('Cum te pot ajuta?');
              for (let i = 0; i < 48; i++) speech.update(1 / 60, 1, 'speaking', .3, camera);
              const gesture = speech.positions.some((x, i) => Math.abs(x - beforeGesture[i]) > .01);
              return { active: a.active, release: a.release, settled: a.settled,
                finite: a.finite && b.finite, difference, gesture, radiusRatio: radius() / quietRadius };
            }""")
            assert physics["finite"] and physics["active"] > .001, physics
            assert physics["release"] > physics["active"] * .5, physics
            assert physics["settled"] < physics["active"] * .03, physics
            assert physics["difference"] < .015, physics
            assert physics["gesture"] and .9 < physics["radiusRatio"] < 1.1, physics
            print("PASS: inertial return, stable springs at 30/120 FPS, phrase gestures without radius pumping")

            def submit(text):
                page.locator("#msg").fill(text)
                page.locator("#msg").press("Enter")
                page.wait_for_function("document.querySelector('#view').dataset.state === 'thinking'")
                assert messages[-1]["type"] == "chat"
                return messages[-1]["id"]

            turn = submit("Salut")
            assert messages[-1]["voice"] == "liana"
            assert page.locator("#speaker, #voice").count() == 0
            ws = connections[-1]
            ws.send(json.dumps({"type": "status", "stage": "speech", "turn": turn}))
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Pregătește vocea')")
            ws.send(json.dumps({"type": "status", "stage": "generating", "turn": turn}))
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Generează răspunsul')")
            print("PASS: progress distinguishes text generation from speech preparation")
            page.wait_for_timeout(500)
            page.screenshot(path=str(artifacts / "thinking.png"))
            ws = connections[-1]
            ws.send(json.dumps({"type": "token", "turn": turn, "text": "Salut!"}))
            ws.send(json.dumps({"type": "speech", "turn": turn, "audio": audio()}))
            ws.send(json.dumps({"type": "done", "turn": turn}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'speaking'")
            page.wait_for_timeout(300)
            page.screenshot(path=str(artifacts / "speaking.png"))
            assert page.locator(".bot").last.inner_text() == "Salut!"
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            print("PASS: idle -> thinking -> speaking -> idle; done waits for audio")

            turn = submit("Pauză între fragmente")
            ws.send(json.dumps({"type": "speech", "turn": turn, "audio": audio()}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'speaking'")
            page.wait_for_timeout(1750)
            assert page.locator("#view").get_attribute("data-state") == "speaking"
            ws.send(json.dumps({"type": "done", "turn": turn}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            print("PASS: speaking shape stays stable between audio fragments")

            turn = submit("Oprește vorbirea")
            ws.send(json.dumps({"type": "speech", "turn": turn, "audio": audio()}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'speaking'")
            page.locator("#stop").click()
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            print("PASS: Stop during speech")

            turn = submit("Oprește procesarea")
            page.locator("#stop").click()
            ws.send(json.dumps({"type": "token", "turn": turn, "text": "IGNORED"}))
            ws.send(json.dumps({"type": "speech", "turn": turn, "audio": audio()}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            assert "IGNORED" not in page.locator("#log").inner_text()
            print("PASS: Stop during processing; stale messages ignored")

            # Delay browser decoding so Stop happens while decodeAudioData is pending.
            page.evaluate("""() => {
              const original = AudioContext.prototype.decodeAudioData;
              AudioContext.prototype.decodeAudioData = async function(...args) {
                await new Promise(resolve => setTimeout(resolve, 700));
                return original.apply(this, args);
              };
            }""")
            turn = submit("Oprește decodarea")
            ws.send(json.dumps({"type": "speech", "turn": turn, "audio": audio()}))
            ws.send(json.dumps({"type": "done", "turn": turn}))
            page.wait_for_timeout(100)
            page.locator("#stop").click()
            page.wait_for_timeout(900)
            assert page.locator("#view").get_attribute("data-state") == "idle"
            print("PASS: Stop invalidates audio still decoding")

            turn = submit("Primul mesaj")
            newer = submit("Al doilea mesaj")
            ws.send(json.dumps({"type": "token", "turn": turn, "text": "STALE"}))
            ws.send(json.dumps({"type": "error", "turn": newer, "text": "Test error", "fatal": True}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            assert "STALE" not in page.locator("#log").inner_text()
            print("PASS: new turn supersedes old turn; terminal error releases state")

            turn = submit("Eroare TTS")
            ws.send(json.dumps({"type": "error", "turn": turn, "text": "TTS test", "fatal": False}))
            ws.send(json.dumps({"type": "token", "turn": turn, "text": "Textul continuă."}))
            page.wait_for_timeout(100)
            assert page.locator("#view").get_attribute("data-state") == "thinking"
            ws.send(json.dumps({"type": "done", "turn": turn}))
            page.wait_for_function("document.querySelector('#view').dataset.state === 'idle'")
            print("PASS: recoverable TTS failure still waits for text completion")

            ws.close()
            page.wait_for_function("document.querySelector('#msg').disabled")
            page.wait_for_function("document.querySelector('#connection').textContent.startsWith('Conectat')", timeout=10000)
            assert len(connections) == 2
            print("PASS: automatic WebSocket reconnect")
            palette = page.evaluate('''async () => {
              const {ParticleSwarm} = await import('./particles.js');
              const swarm = new ParticleSwarm(1000);
              const samples = [0,4,5,6,12,18].map(t => {
                swarm.updatePalette(t);
                return swarm.uniforms.uIdleLow.value.toArray();
              });
              swarm.points.geometry.dispose(); swarm.points.material.dispose();
              return samples;
            }''')
            assert palette[0] == palette[1] == palette[5], palette
            assert palette[0] != palette[2] != palette[3] != palette[4], palette
            print("PASS: automatic palette hold, gradual crossfade and complete cycle")
            page.locator(".appearance summary").click()
            assert page.locator("#avatar-palette").count() == 0
            for control, value in [("brightness", "1.3"), ("density", "4000"), ("interaction", "0.8")]:
                page.locator(f"#avatar-{control}").evaluate("(el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }", value)
            page.locator("#avatar-trails").uncheck()
            page.wait_for_timeout(300)
            assert page.locator("#avatar-density-value").inner_text() == "4000"
            page.screenshot(path=str(artifacts / "customized.png"))
            page.reload()
            page.wait_for_function("document.querySelector('#connection').textContent.startsWith('Conectat')")
            assert page.locator("#avatar-palette").count() == 0
            assert page.locator("#avatar-brightness").input_value() == "1.3"
            assert page.locator("#avatar-density").input_value() == "4000"
            assert not page.locator("#avatar-trails").is_checked()
            print("PASS: appearance controls update and persist after reload")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(300)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(artifacts / "mobile.png"))
            assert not errors, errors
            print("PASS: mobile layout; no JavaScript or shader console errors")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run()
