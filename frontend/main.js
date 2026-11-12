import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { ParticleSwarm } from "./particles.js";
import { VoiceEffect } from "./voice-effect.js";
import { mountAvatarSettings } from "./avatar-settings.js";
import { CharacterAvatar, activeSpeechPose } from "./character.js";
import { mountStudio } from "./studio-ui.js";
import { mountMicrophone } from "./microphone.js";
import { CharacterStage } from "./character-stage.js";
import { mountCharacterControls } from "./character-controls.js";

const view = document.getElementById("view");
const statusEl = document.getElementById("status");
const connectionEl = document.getElementById("connection");
const logEl = document.getElementById("log");
const msgEl = document.getElementById("msg");
const langEl = document.getElementById("lang");
const stopButton = document.getElementById("stop");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
view.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = null;
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(0, 0.3, 6.5);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.enablePan = false;
controls.minDistance = 4;
controls.maxDistance = 10;
const swarm = new ParticleSwarm();
scene.add(swarm.group);
mountAvatarSettings(swarm);
view.dataset.avatar = "particles";
const character = new CharacterAvatar();
scene.add(character.group);
const characterStage = new CharacterStage();
scene.add(characterStage.group);
const avatarSelector = document.getElementById("avatar-mode");
const avatarLoad = document.getElementById("avatar-load");
const appearance = document.querySelector(".appearance");
const hint = document.querySelector(".hint");
let avatarMode = "particles", selection = 0;
const cameras = {};
function describeAvatar(mode) {
  document.getElementById("view-title").textContent = mode === "character" ? "Personaj 3D" : "Roi de particule";
  const voice = langEl.value === "en" ? "Lessac" : mode === "character" ? "Raluca" : "Liana";
  document.getElementById("voice-label").textContent = `${voice} · voce ${mode === "character" ? "naturală" : "robotică"}`;
  document.getElementById("mode-heading").textContent = mode === "character" ? "Mai mult decât text." : "Conversația prinde formă.";
  document.getElementById("mode-description").textContent = mode === "character"
    ? "Un personaj care vorbește, clipește și urmărește cursorul. Gura este animată în sincron cu vocea."
    : "Un roi care orbitează în repaus și se strânge la procesare. În vorbire, forma și lumina însoțesc vocea, iar particulele reacționează la cursor.";
}
async function selectAvatar(mode) {
  const request = ++selection;
  avatarLoad.textContent = mode === "character" && !character.loaded ? "Se încarcă avatarul…" : "";
  try {
    if (mode === "character") {await character.load();characterTools.modelLoaded();}
    if (request !== selection) return;
    cameras[avatarMode] = {position: camera.position.clone(), target: controls.target.clone(),
      min: controls.minDistance, max: controls.maxDistance, fov: camera.fov, near: camera.near};
    avatarMode = mode;
    voiceEffect.setMode(mode === "particles" ? "robot" : "natural");
    character.group.visible = mode === "character";
    characterStage.group.visible = mode === "character";
    characterTools.setVisible(mode === "character");
    swarm.group.visible = mode === "particles";
    swarm.setPointer(0, 0, false);
    swarm.historyReady = false;
    character.setLook(0, 0, false);
    const saved = cameras[mode];
    if (saved) {
      camera.position.copy(saved.position); controls.target.copy(saved.target);
      camera.fov = saved.fov; camera.near = saved.near;
      controls.minDistance = saved.min; controls.maxDistance = saved.max;
      camera.updateProjectionMatrix(); controls.update();
    } else character.frameCamera(camera, controls);
    appearance.hidden = mode !== "particles";
    hint.textContent = mode === "particles"
      ? "Treci cursorul printre particule · Trage pentru rotire · Scroll pentru zoom"
      : "Personaj 3D · Trage pentru rotire · Scroll pentru zoom";
    view.dataset.avatar = mode;
    avatarSelector.value = mode;
    describeAvatar(mode);
    avatarLoad.textContent = "";
    try { localStorage.setItem("avatar-mode", mode); } catch { /* Optional preference. */ }
  } catch (error) {
    if (request !== selection) return;
    avatarSelector.value = avatarMode;
    appearance.hidden = avatarMode !== "particles";
    characterTools.setVisible(avatarMode === "character");
    describeAvatar(avatarMode);
    avatarLoad.textContent = `Nu pot încărca avatarul: ${error.message}. Poți folosi roiul.`;
  }
}
avatarSelector.addEventListener("change", () => selectAvatar(avatarSelector.value));
langEl.addEventListener("change", () => describeAvatar(avatarMode));
let preferred = "character";
try { if (localStorage.getItem("avatar-mode") === "particles") preferred = "particles"; } catch { /* Default avatar. */ }
const characterTools = mountCharacterControls({character,stage:characterStage,view,
  reframe:()=>{if(character.loaded)character.frameCamera(camera,controls);},
  interrupt:()=>{microphone?.cancel();interruptResponse();}});
const pointer = new THREE.Vector2();
function movePointer(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1,
              1 - ((event.clientY - rect.top) / rect.height) * 2);
  const inside = Math.abs(pointer.x) <= 1 && Math.abs(pointer.y) <= 1;
  const active = inside && event.buttons === 0 && event.pointerType !== "touch";
  swarm.setPointer(pointer.x, pointer.y, active && avatarMode === "particles");
  character.setPointer(pointer, camera, active && avatarMode === "character");
}
const releasePointer = () => { swarm.setPointer(pointer.x, pointer.y, false); character.setLook(0, 0, false); };
renderer.domElement.addEventListener("pointermove", movePointer);
renderer.domElement.addEventListener("pointerdown", releasePointer);
renderer.domElement.addEventListener("pointerleave", releasePointer);
renderer.domElement.addEventListener("pointercancel", releasePointer);
addEventListener("pointerup", event => {
  if (event.target === renderer.domElement) movePointer(event);
  else releasePointer();
});
addEventListener("blur", releasePointer);
new ResizeObserver(() => {
  const w = Math.max(view.clientWidth, 1), h = Math.max(view.clientHeight, 1);
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}).observe(view);

const audioCtx = new AudioContext();
const analyser = audioCtx.createAnalyser();
analyser.fftSize = 1024;
analyser.connect(audioCtx.destination);
const voiceEffect = new VoiceEffect(audioCtx, analyser, "robot");
selectAvatar(preferred);
const samples = new Float32Array(analyser.fftSize);
const clips = new Set();
let nextStart = 0;
let turn = 0;
let current = null;
let botLine = null;
let ws;
let reconnectTimer;
let shuttingDown = false;
let serviceLabel = "Conectat";
let microphone;
const audioArchive = [];
const studio = mountStudio({
  resetCamera() {
    if (avatarMode === "character") character.frameCamera(camera, controls);
    else {
      camera.fov = 45; camera.near = .1; camera.position.set(0, .3, 6.5);
      controls.target.set(0, 0, 0); controls.minDistance = 4; controls.maxDistance = 10;
      camera.updateProjectionMatrix(); controls.update();
    }
    swarm.setPointer(0, 0, false); character.setLook(0, 0, false);
  },
  newConversation() {
    microphone?.cancel();
    stopLocal();
    for (const session of audioArchive) session.recordings.length = 0;
    audioArchive.length = 0;
    clearTimeout(reconnectTimer);
    if (ws) {
      ws.onopen = ws.onclose = ws.onerror = ws.onmessage = null;
      ws.close();
    }
    logEl.replaceChildren();
    msgEl.value = ""; botLine = null;
    connect();
  },
});
microphone = mountMicrophone({input:msgEl, language:langEl,
  interrupt:interruptResponse, syncComposer:studio.syncComposer, notify:studio.notify});
const articulationDialog = document.getElementById("articulation-dialog");
document.getElementById("speech-check").addEventListener("click", () => articulationDialog.showModal());
document.getElementById("close-articulation").addEventListener("click", () => articulationDialog.close());
for (const button of document.querySelectorAll("[data-speech-sample]")) {
  button.addEventListener("click", () => { articulationDialog.close(); playSample(button.dataset.speechSample); });
}
fetch("/api/config").then(response => {
  if (!response.ok) throw new Error("Configurație indisponibilă");
  return response.json();
}).then(config => {
  serviceLabel = "Conectat";
  document.getElementById("model-label").textContent = config.model || "Model local";
  if (ws?.readyState === WebSocket.OPEN) connectionEl.textContent = serviceLabel;
}).catch(() => { /* Connection remains usable when status details are unavailable. */ });

function addLine(cls, text) {
  const line = document.createElement("div");
  line.className = cls;
  line.dataset.label = cls === "user" ? "TU" : cls === "bot" ? "ASISTENT" : "NOTIFICARE";
  line.textContent = text;
  const row = document.createElement("div"); row.className = "message-row";
  row.append(line); logEl.append(row);
  studio.syncMessages();
  logEl.scrollTop = logEl.scrollHeight;
  return line;
}

function stopLocal() {
  // Invalidate scheduled audio and decodes still awaiting completion.
  if (botLine && !botLine.textContent.trim()) botLine.textContent = "Răspuns întrerupt.";
  current?.actions?.refresh(current);
  current?.request?.abort();
  turn++;
  current = null;
  for (const clip of clips) {
    clip.src.onended = null;
    try { clip.src.stop(); } catch { /* Already ended. */ }
    clip.src.disconnect();
  }
  clips.clear();
  nextStart = 0;
}

function interruptResponse() {
  stopLocal();
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type:"stop"}));
}

function rememberAudio(session, recording) {
  if (session.replay || session.preview) return;
  session.recordings.push(recording);
  if (!audioArchive.includes(session)) audioArchive.push(session);
  const seconds = () => audioArchive.reduce((sum, item) => sum + item.recordings.reduce((n,r) => n + r.buffer.duration,0),0);
  while (audioArchive.length > 6 || seconds() > 180) {
    const expired = audioArchive.shift(); expired.recordings.length = 0;
    expired.actions?.audioAvailable(false);
  }
  session.actions?.audioAvailable(session.recordings.length > 0);
}

async function replayResponse(original) {
  const recordings = [...original.recordings];
  if (!recordings.length) return;
  characterTools.prepareSpeech();
  microphone.cancel(); interruptResponse();
  const session = {done:true,pending:1,hasSpoken:false,replay:true}; current = session;
  try {
    await audioCtx.resume();
    for (const recording of recordings) await enqueueSpeech(recording,session);
  } catch (error) { if (current === session) studio.notify(`Redare audio: ${error.message}`); }
  finally { session.pending = 0; }
}

async function playSample(sample) {
  characterTools.prepareSpeech();
  microphone.cancel(); interruptResponse();
  const session = {done:false,pending:1,preview:true,stage:"speech",stageSince:performance.now(),request:new AbortController()};
  current = session;
  try {
    await audioCtx.resume();
    if (current !== session) return;
    const response = await fetch("/api/speech-sample",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({sample,lang:langEl.value,voice:avatarMode === "particles" ? "liana" : "raluca"}),signal:session.request.signal});
    const speech = await response.json();
    if (current !== session) return;
    if (!response.ok) throw new Error(speech.detail || "Testul vocal nu este disponibil.");
    studio.notify(`Test: ${speech.text}`);
    await enqueueSpeech(speech,session);
  } catch (error) { if (current === session && error.name !== "AbortError") studio.notify(error.message); }
  finally { session.done = true; session.pending = 0; }
}

async function enqueueSpeech(message, session) {
  if (current !== session) return;
  const buffer = message.buffer || await audioCtx.decodeAudioData(Uint8Array.from(atob(message.audio), c => c.charCodeAt(0)).buffer);
  if (current !== session) return;
  rememberAudio(session,{buffer,text:message.text || "",visemes:message.visemes || []});
  const src = audioCtx.createBufferSource();
  src.buffer = buffer;
  src.connect(voiceEffect.input);
  const start = Math.max(audioCtx.currentTime + 0.04, nextStart);
  const clip = { src, start, end: start + buffer.duration, text: message.text || "",
    visemes: Array.isArray(message.visemes) ? message.visemes : [], gestured: false };
  src.onended = () => { clips.delete(clip); src.disconnect(); };
  clips.add(clip);
  try {
    src.start(start);
    nextStart = clip.end;
  } catch (error) {
    clips.delete(clip);
    src.disconnect();
    throw error;
  }
}

function connect() {
  if (shuttingDown) return;
  connectionEl.textContent = "Se conectează…";
  connectionEl.parentElement.dataset.state = "connecting";
  msgEl.disabled = true;
  studio.syncComposer();
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws = socket;
  socket.onopen = () => {
    connectionEl.textContent = serviceLabel;
    connectionEl.parentElement.dataset.state = "online";
    msgEl.disabled = false;
    studio.syncComposer();
  };
  socket.onmessage = (event) => {
    let m;
    try { m = JSON.parse(event.data); }
    catch { addLine("err", "Mesaj invalid primit de la server."); return; }
    const session = current;
    if (!session || m.turn !== turn) return;
    if (m.type === "status") {
      if (["generating", "speech"].includes(m.stage) && session.stage !== m.stage) {
        session.stage = m.stage;
        session.stageSince = performance.now();
      }
    } else if (m.type === "token") {
      if (m.text && session.firstTextMs == null) session.firstTextMs = performance.now() - session.startedAt;
      const following = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 80;
      botLine.textContent += m.text;
      session.actions?.refresh(session);
      if (following) logEl.scrollTop = logEl.scrollHeight;
    } else if (m.type === "speech") {
      session.pending++;
      session.chain = session.chain.then(() => enqueueSpeech(m, session))
        .catch(error => {
          if (current === session) addLine("err", `Redare audio: ${error.message}`);
        }).finally(() => { session.pending--; });
    } else if (m.type === "done") {
      session.done = true;
      if (!botLine.textContent.trim()) botLine.textContent = "Nu am primit un răspuns.";
      session.actions?.refresh(session);
    } else if (m.type === "error") {
      addLine("err", m.text);
      if (m.fatal !== false) {
        session.done = true;
        if (!botLine.textContent.trim()) botLine.textContent = "Răspuns indisponibil.";
        session.actions?.refresh(session);
      }
    }
  };
  socket.onclose = () => {
    microphone.cancel();
    stopLocal();
    msgEl.disabled = true;
    studio.syncComposer();
    connectionEl.parentElement.dataset.state = "offline";
    connectionEl.textContent = "Deconectat · Reîncerc în 2 secunde…";
    if (!shuttingDown) reconnectTimer = setTimeout(connect, 2000);
  };
  socket.onerror = () => {
    connectionEl.textContent = "Conexiune indisponibilă";
    connectionEl.parentElement.dataset.state = "offline";
  };
}

document.getElementById("chat").addEventListener("submit", async event => {
  event.preventDefault();
  const text = msgEl.value.trim();
  if (!text || ws?.readyState !== WebSocket.OPEN) return;
  characterTools.prepareSpeech();
  microphone.cancel();
  stopLocal();
  const session = { done: false, pending: 0, chain: Promise.resolve(), stage: "generating", stageSince: performance.now(),
    voice: avatarMode === "particles" ? "liana" : "raluca",startedAt:performance.now(),recordings:[] };
  current = session;
  addLine("user", text);
  botLine = addLine("bot", "");
  session.actions = studio.attachResponse(botLine,() => replayResponse(session));
  session.actions.refresh(session);
  msgEl.value = "";
  studio.syncComposer();
  try {
    // Called inside the user gesture, before requesting speech.
    await audioCtx.resume();
    if (current !== session) return;
    if (ws.readyState !== WebSocket.OPEN) throw new Error("Conexiunea s-a închis.");
    ws.send(JSON.stringify({ type: "chat", id: turn, text, lang: langEl.value, voice: session.voice }));
  } catch (error) {
    if (current === session) {
      stopLocal();
      addLine("err", `Nu pot porni conversația: ${error.message}`);
    }
  }
});
stopButton.onclick = () => {
  microphone.cancel(); interruptResponse();
};

let visualState;
const labels = { idle: "În repaus", thinking: "Procesează…", speaking: "Răspunde" };
const clock = new THREE.Clock();
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  const now = audioCtx.currentTime;
  const playing = audioCtx.state === "running" && [...clips].some(c => now >= c.start && now < c.end);
  if (playing) {
    if (current && !current.preview && !current.replay && current.firstAudioMs == null) {
      current.firstAudioMs = performance.now() - current.startedAt;
      current.actions?.refresh(current);
    }
    for (const clip of clips) {
      if (!clip.gestured && now >= clip.start && now < clip.end) {
        swarm.beginPhrase(clip.text);
        character.beginPhrase(clip.text, clock.elapsedTime);
        clip.gestured = true;
      }
    }
  }
  const waiting = current && (!current.done || current.pending > 0 || clips.size > 0);
  if (playing && current) current.hasSpoken = true;
  // Keep the speaking shape between TTS fragments instead of contracting each time.
  const speaking = playing || (waiting && current.hasSpoken);
  const state = speaking ? "speaking" : waiting ? "thinking" : "idle";
  if (state !== visualState) {
    visualState = state;
    view.dataset.state = state;
  }
  let statusText = labels[state];
  if (state === "thinking" && current && !current.done) {
    statusText = current.stage === "speech" ? "Pregătește vocea…" : "Generează răspunsul…";
    const elapsed = Math.floor((performance.now() - current.stageSince) / 1000);
    if (elapsed >= 10) statusText += ` · ${elapsed} sec`;
  }
  if (statusEl.textContent !== statusText) statusEl.textContent = statusText;
  stopButton.disabled = !waiting;
  let rms = 0;
  if (playing) {
    analyser.getFloatTimeDomainData(samples);
    for (const sample of samples) rms += sample * sample;
    rms = Math.sqrt(rms / samples.length);
  }
  controls.update();
  if (avatarMode === "character") character.updateCameraFocus(camera, controls);
  if (avatarMode === "particles") swarm.update(dt, clock.elapsedTime, state, rms, camera);
  else character.update(dt, clock.elapsedTime, state, rms,
    audioCtx.state === "running" ? activeSpeechPose(clips, now - (audioCtx.outputLatency || 0)) : "REST");
  renderer.render(scene, camera);
  characterTools.update(performance.now());
}
renderer.setAnimationLoop(frame);
connect();
addEventListener("pagehide", () => {
  shuttingDown = true;
  clearTimeout(reconnectTimer);
  stopLocal();
  ws?.close();
});
addEventListener("pageshow", event => { if (event.persisted) { shuttingDown = false; connect(); } });
