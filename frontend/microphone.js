export function mountMicrophone({ input, language, interrupt, syncComposer, notify }) {
  const button = document.getElementById("microphone"), status = document.getElementById("microphone-status");
  const tools = document.getElementById("microphone-tools"), devices = document.getElementById("microphone-device");
  const meter = document.getElementById("microphone-level");
  let state = "idle", epoch = 0, recorder, stream, request, limit;
  let meterContext, meterTimer, monitoring = 0, deviceName = "microfonul selectat";
  let chosenDevice;
  try { chosenDevice = localStorage.getItem("microphone-device") || ""; } catch { chosenDevice = ""; }
  async function refreshDevices() {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const inputs = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "audioinput" && d.deviceId);
      const selected = chosenDevice || devices.value;
      devices.replaceChildren(new Option("Microfon implicit", ""));
      inputs.forEach((device, index) => devices.add(new Option(device.label || `Microfon ${index + 1}`, device.deviceId)));
      if ([...devices.options].some(option => option.value === selected)) devices.value = selected;
      else chosenDevice = "";
      if (inputs.some(d => d.label) || state !== "idle") tools.hidden = false;
    } catch { /* Some embedded browsers restrict device enumeration. */ }
  }
  devices.addEventListener("change", () => {
    chosenDevice = devices.value;
    try { localStorage.setItem("microphone-device", chosenDevice); } catch { /* Optional preference. */ }
    if (state !== "idle") cancel();
    notify("Microfon selectat. Apasă butonul pentru o nouă înregistrare.");
  });
  const labels = {idle:"Dictează un mesaj", requesting:"Anulează accesul la microfon", recording:"Oprește înregistrarea", transcribing:"Anulează transcrierea"};
  function show(next, text = "") {
    state = next; button.dataset.state = next; button.title = labels[next];
    button.setAttribute("aria-label", labels[next]); button.setAttribute("aria-pressed", String(next === "recording"));
    status.textContent = text; status.hidden = !text;
  }
  function release() {
    clearTimeout(limit); clearInterval(meterTimer); monitoring++;
    stream?.getTracks().forEach(t => t.stop()); stream = null;
    meter.value = 0;
    if (meterContext) { meterContext.close().catch(() => {}); meterContext = null; }
  }
  async function monitor(captured, generation) {
    const id = ++monitoring, started = performance.now();
    let heard = false;
    try {
      const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
      const context = new Context(); meterContext = context;
      const analyser = context.createAnalyser(); analyser.fftSize = 1024;
      context.createMediaStreamSource(captured).connect(analyser);
      await context.resume();
      if (generation !== epoch || id !== monitoring) return;
      const samples = new Float32Array(analyser.fftSize);
      meterTimer = setInterval(() => {
        if (generation !== epoch || state !== "recording") return;
        analyser.getFloatTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, x) => sum + x*x,0) / samples.length);
        meter.value = Math.min(1, rms * 14);
        if (rms > .003) heard = true;
        const seconds = Math.floor((performance.now() - started)/1000);
        const warning = seconds >= 3 && !heard ? " · Semnal foarte slab: verifică intrarea audio aleasă." : "";
        status.textContent = `Înregistrează ${seconds} s · ${deviceName}. Apasă din nou pentru transcriere${warning}`;
      },150);
    } catch { /* Recording still works when the optional level meter is unavailable. */ }
  }
  function cancel() {
    epoch++; request?.abort(); request = null;
    if (recorder?.state === "recording") recorder.stop();
    recorder = null; release(); show("idle");
  }
  async function start() {
    if (input.disabled) { notify("Conectează aplicația înainte de a folosi microfonul."); return; }
    const generation = ++epoch, lang = language.value;
    interrupt(); show("requesting", "Permite accesul la microfon în browser.");
    try {
      const captured = await navigator.mediaDevices.getUserMedia({audio:{
        ...(chosenDevice ? {deviceId:{exact:chosenDevice}} : {}),
        echoCancellation:true,noiseSuppression:true,autoGainControl:true,
      }});
      if (generation !== epoch) { captured.getTracks().forEach(t => t.stop()); return; }
      stream = captured;
      deviceName = captured.getAudioTracks?.()[0]?.label || "microfonul selectat";
      tools.hidden = false;
      await refreshDevices();
      if (generation !== epoch) return;
      const mimeType = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find(t => MediaRecorder.isTypeSupported(t));
      const recording = new MediaRecorder(stream, {...(mimeType ? {mimeType} : {}), audioBitsPerSecond:64000});
      recorder = recording;
      const parts = [];
      recording.ondataavailable = e => { if (e.data.size) parts.push(e.data); };
      recording.onerror = () => { if (generation === epoch) { cancel(); notify("Înregistrarea nu a reușit. Verifică microfonul."); } };
      recording.onstop = async () => {
        if (generation !== epoch) return;
        release(); recorder = null;
        const blob = new Blob(parts, {type:recording.mimeType || "audio/webm"});
        if (!blob.size) { show("idle"); notify("Nu am primit audio. Încearcă din nou."); return; }
        show("transcribing", "Transcrie local… Apasă microfonul pentru anulare.");
        request = new AbortController(); const controller = request;
        limit = setTimeout(() => controller.abort(), 90000);
        try {
          const response = await fetch(`/api/transcribe?lang=${encodeURIComponent(lang)}`, {
            method:"POST", body:blob, headers:{"Content-Type":blob.type}, signal:controller.signal,
          });
          const result = await response.json();
          if (generation !== epoch) return;
          if (!response.ok) throw new Error(result.detail || "Transcrierea nu este disponibilă.");
          if (!result.text?.trim()) {
            notify("Nu am detectat vorbire. Alege microfonul corect din Intrare audio și verifică dacă indicatorul de nivel se mișcă când vorbești.");
            return;
          }
          const existing = input.value.trim();
          input.value = `${existing}${existing ? "\n" : ""}${result.text.trim()}`.slice(0,4000);
          syncComposer(); input.focus(); notify("Textul este gata. Verifică-l, apoi trimite mesajul.");
        } catch (error) {
          if (generation === epoch) notify(error.name === "AbortError" ? "Transcriere întreruptă. Încearcă din nou." : error.message);
        } finally { if (generation === epoch) { clearTimeout(limit); request = null; show("idle"); } }
      };
      recording.start(250); show("recording", "Ascultă… Apasă din nou pentru transcriere · maximum 60 secunde.");
      monitor(captured,generation);
      limit = setTimeout(() => {
        if (generation === epoch && recording.state === "recording") {
          show("transcribing", "Pregătește înregistrarea…"); recording.stop();
        }
      },60000);
    } catch (error) {
      if (generation !== epoch) return;
      release(); show("idle");
      notify(error.name === "NotAllowedError" ? "Accesul la microfon a fost refuzat. Îl poți permite din setările browserului."
        : error.name === "NotFoundError" ? "Nu am găsit un microfon conectat."
        : error.name === "NotReadableError" ? "Microfonul nu poate fi deschis. Verifică accesul în Windows și dacă altă aplicație îl folosește."
        : error.name === "OverconstrainedError" ? "Microfonul salvat nu mai este disponibil. Selectează alt dispozitiv din Intrare audio."
        : "Microfonul nu este disponibil în acest moment.");
    }
  }
  if (!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder) {
    button.disabled = true; button.title = "Microfonul necesită localhost sau HTTPS și un browser compatibil.";
    status.hidden = false; status.textContent = button.title;
  } else {
    refreshDevices();
    navigator.mediaDevices.addEventListener?.("devicechange",refreshDevices);
  }
  button.addEventListener("click", () => {
    if (state === "idle") start();
    else if (state === "recording") {
      clearTimeout(limit); show("transcribing", "Pregătește înregistrarea…");
      if (recorder?.state === "recording") recorder.stop();
    }
    else cancel();
  });
  addEventListener("pagehide",cancel);
  return {cancel};
}
