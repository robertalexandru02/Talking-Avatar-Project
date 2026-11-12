const poses = {BMP:{open:0,width:24},A:{open:.85,width:23},O:{open:.65,width:15},U:{open:.25,width:10}};
let selected = "BMP", playing = false, started = 0, last = performance.now(), open = 0, width = 24;
const run = document.getElementById("run-demo"), speed = document.getElementById("lerp-speed");
function select(name) {
  selected = name;
  document.querySelectorAll("[data-viseme]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.viseme === name)));
}
document.querySelectorAll("[data-viseme]").forEach(button => button.addEventListener("click", () => {
  playing = false; run.textContent = "Pornește demonstrația"; run.setAttribute("aria-pressed","false"); select(button.dataset.viseme);
}));
speed.addEventListener("input",() => { document.getElementById("lerp-value").value = speed.value; });
run.addEventListener("click",() => {
  playing = !playing; started = performance.now();
  run.textContent = playing ? "Oprește demonstrația" : "Pornește demonstrația";
  run.setAttribute("aria-pressed",String(playing));
});
function animate(time) {
  const dt = Math.min((time-last)/1000,.05); last = time;
  if (playing) select(["BMP","A","O","U"][Math.floor((time-started)/950)%4]);
  const factor = 1-Math.exp(-Number(speed.value)*dt);
  open += (poses[selected].open-open)*factor; width += (poses[selected].width-width)*factor;
  document.getElementById("demo-mouth").setAttribute("rx",width);
  document.getElementById("demo-mouth").setAttribute("ry",2+open*22);
  document.getElementById("jaw-weight").value = open.toFixed(2);
  document.getElementById("weight-fill").style.width = `${open*100}%`;
  document.querySelectorAll("[data-step]").forEach((card,i) => card.classList.toggle("active",playing && Math.floor((time-started)/950)%3 === i));
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
