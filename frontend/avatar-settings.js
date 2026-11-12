// Persist only appearance preferences; conversation and audio remain transient.
export function mountAvatarSettings(swarm) {
  const defaults = { brightness: 1.4, density: 9000, interaction: 1.7, trails: true };
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem("particle-appearance") || "{}") || {}; } catch { /* Storage may be disabled. */ }
  const settings = { ...defaults, presetVersion: 2 };
  for (const key of ["brightness", "density", "interaction"]) {
    // Apply the new preset once, including browsers with the previous defaults.
    if (saved.presetVersion === 2 && typeof saved[key] === "number" && Number.isFinite(saved[key])) settings[key] = saved[key];
  }
  if (typeof saved.trails === "boolean") settings.trails = saved.trails;
  for (const key of Object.keys(defaults)) {
    const input = document.getElementById(`avatar-${key}`);
    if (input.type === "checkbox") input.checked = settings[key];
    else input.value = String(settings[key]);
    const update = () => {
      settings[key] = input.type === "checkbox" ? input.checked : input.tagName === "SELECT" ? input.value : Number(input.value);
      swarm.setAppearance({ [key]: settings[key] });
      const output = document.getElementById(`avatar-${key}-value`);
      if (output) output.textContent = key === "density" ? String(settings[key]) : `${Math.round(settings[key] * 100)}%`;
    };
    input.addEventListener("input", () => {
      update();
      try { localStorage.setItem("particle-appearance", JSON.stringify(settings)); } catch { /* Optional persistence. */ }
    });
    update();
  }
  try { localStorage.setItem("particle-appearance", JSON.stringify(settings)); } catch { /* Optional persistence. */ }
}
