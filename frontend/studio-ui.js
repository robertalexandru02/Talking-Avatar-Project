// Presentation controls; conversation and speech remain owned by main.js.
export function mountStudio({ newConversation, resetCamera }) {
  const input = document.getElementById("msg");
  const form = document.getElementById("chat");
  const log = document.getElementById("log");
  const send = document.getElementById("send");
  const download = document.getElementById("export-chat");
  let toastTimer;
  function notify(message) {
    const toast = document.getElementById("toast");
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
  }
  function syncComposer() {
    send.disabled = input.disabled || !input.value.trim();
    document.getElementById("char-count").textContent = `${input.value.length} / 4000`;
    input.style.height = "auto";
    input.style.height = `${Math.min(140, Math.max(56, input.scrollHeight))}px`;
  }
  function syncMessages() {
    const count = log.querySelectorAll(".user").length;
    document.getElementById("message-count").textContent = count;
    document.getElementById("empty-state").hidden = log.children.length > 0;
    download.disabled = count === 0;
  }
  input.addEventListener("input", syncComposer);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!send.disabled) form.requestSubmit();
    }
  });
  for (const button of document.querySelectorAll("[data-prompt]")) {
    button.addEventListener("click", () => {
      if (input.disabled) { notify("Așteaptă conectarea la server."); return; }
      input.value = button.dataset.prompt;
      syncComposer();
      input.focus();
    });
  }
  document.getElementById("new-chat").addEventListener("click", () => {
    newConversation();
    syncComposer(); syncMessages();
    notify("Ai început o conversație nouă.");
  });
  document.getElementById("reset-camera").addEventListener("click", () => {
    resetCamera();
    notify("Camera a revenit la poziția inițială.");
  });
  const fullscreen = document.getElementById("fullscreen");
  fullscreen.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.querySelector(".stage-card").requestFullscreen();
    } catch { notify("Ecranul complet nu este disponibil în acest browser."); }
  });
  document.addEventListener("fullscreenchange", () => {
    const label = document.fullscreenElement ? "Ieși din ecran complet" : "Ecran complet";
    fullscreen.title = label; fullscreen.setAttribute("aria-label", label);
  });
  download.addEventListener("click", () => {
    const lines = [...log.querySelectorAll(".user, .bot, .err")].filter(line => line.textContent.trim())
      .map(line => `${line.dataset.label}\n${line.textContent}`);
    const text = `Talking Avatar — conversație\n${new Date().toLocaleString("ro-RO")}\n\n${lines.join("\n\n")}`;
    const url = URL.createObjectURL(new Blob([text], {type: "text/plain;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = url; link.download = `conversatie-${new Date().toISOString().slice(0,10)}.txt`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("Conversația a fost exportată.");
  });
  function attachResponse(line, replay) {
    const actions = document.createElement("div"); actions.className = "response-actions";
    const copy = document.createElement("button"); copy.type = "button"; copy.textContent = "Copiază";
    copy.setAttribute("aria-label", "Copiază răspunsul");
    const play = document.createElement("button"); play.type = "button"; play.textContent = "Reascultă";
    play.setAttribute("aria-label", "Reascultă răspunsul"); play.disabled = true;
    const stats = document.createElement("span"); stats.className = "response-timing";
    actions.append(copy, play, stats); line.parentElement.append(actions);
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(line.textContent); notify("Răspuns copiat."); }
      catch { notify("Copierea nu este disponibilă. Poți selecta și copia textul manual."); }
    });
    play.addEventListener("click", replay);
    return {
      refresh(session) {
        copy.disabled = !line.textContent.trim();
        if (session?.replay) return;
        const values = [];
        if (session?.firstTextMs != null) values.push(`Text ${(session.firstTextMs/1000).toFixed(1)} s`);
        if (session?.firstAudioMs != null) values.push(`Voce ${(session.firstAudioMs/1000).toFixed(1)} s`);
        stats.textContent = values.join(" · ");
        stats.title = "Timp de la trimitere până la primul text și prima redare audio.";
      },
      audioAvailable(available) {
        play.disabled = !available;
        play.title = available ? "Redă audio-ul disponibil al acestui răspuns" : "Audio indisponibil sau eliminat din memoria sesiunii";
      },
    };
  }
  syncComposer(); syncMessages();
  return { syncComposer, syncMessages, notify, attachResponse };
}
