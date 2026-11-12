const DEFAULTS={clothes:"#ffffff",hair:"#ffffff",glasses:true,framing:"portrait",theme:"studio"};
const WATCH=["jawOpen","mouthClose","mouthFunnel","mouthPucker","mouthSmileLeft","eyeBlinkLeft","eyeBlinkRight","browInnerUp"];

export function mountCharacterControls({character,stage,view,reframe,interrupt}) {
  let saved={};
  try {saved=JSON.parse(localStorage.getItem("character-appearance")||"{}");}catch{/* Optional preference. */}
  const settings={...DEFAULTS};
  for(const name of ["clothes","hair"])if(/^#[0-9a-f]{6}$/i.test(saved?.[name]||""))settings[name]=saved[name];
  if(typeof saved?.glasses==="boolean")settings.glasses=saved.glasses;
  if(["portrait","full"].includes(saved?.framing))settings.framing=saved.framing;
  if(["studio","gallery","night"].includes(saved?.theme))settings.theme=saved.theme;
  character.setAppearance(settings);stage.setTheme(settings.theme);view.dataset.scene=settings.theme;
  const button=document.createElement("button");button.id="character-tools-button";button.type="button";button.className="icon-button";
  button.setAttribute("aria-label","Personalizare și laborator grafic");button.title="Personalizare și laborator grafic";
  button.setAttribute("aria-expanded","false");button.setAttribute("aria-controls","character-tools");button.hidden=true;
  button.innerHTML='<svg aria-hidden="true"><use href="#i-sliders"/></svg>';
  document.querySelector(".stage-actions").prepend(button);
  const panel=document.createElement("aside");panel.id="character-tools";panel.className="character-tools";panel.hidden=true;
  panel.setAttribute("aria-label","Setările personajului și laborator grafic");
  panel.innerHTML=`<div class="character-tools-heading"><span>PERSONAJ 3D</span><button type="button" id="close-character-tools" aria-label="Închide setările">×</button></div>
    <div class="character-tabs" role="tablist" aria-label="Controale personaj"><button type="button" role="tab" id="appearance-tab" aria-controls="character-appearance" aria-selected="true">Aspect</button><button type="button" role="tab" id="inspector-tab" aria-controls="character-inspector" aria-selected="false" tabindex="-1">Laborator grafic</button></div>
    <section id="character-appearance" role="tabpanel" aria-labelledby="appearance-tab">
      <p class="character-note">Personalizează modelul existent. Nuanțele păstrează textura hainelor și a părului.</p>
      <label for="character-clothes">Nuanța ținutei<input type="color" id="character-clothes" value="#ffffff"></label>
      <label for="character-hair">Nuanța părului<input type="color" id="character-hair" value="#ffffff"></label>
      <label for="character-glasses">Ochelari<input type="checkbox" id="character-glasses" checked></label>
      <label for="character-theme">Ambianță<select id="character-theme"><option value="studio">Studio · verde rece</option><option value="gallery">Galerie · lumină caldă</option><option value="night">Noapte · albastru</option></select></label>
      <label for="character-framing">Încadrare<select id="character-framing"><option value="portrait">Portret</option><option value="full">Corp întreg</option></select></label>
      <button type="button" id="reset-character-appearance" class="character-reset">Resetează aspectul</button>
    </section>
    <section id="character-inspector" role="tabpanel" aria-labelledby="inspector-tab" hidden>
      <p id="character-model-info" class="character-note">Se încarcă datele modelului…</p>
      <label for="inspect-skeleton">Afișează scheletul<input type="checkbox" id="inspect-skeleton"></label>
      <label for="inspect-wireframe">Rețea de poligoane<input type="checkbox" id="inspect-wireframe"></label>
      <label for="inspect-manual">Control manual al feței<input type="checkbox" id="inspect-manual"></label>
      <p class="character-note">Controlul manual oprește vocea. Un mesaj nou sau un test de articulare reactivează automat lip-sync-ul.</p>
      <label for="inspect-shape">Morph target<select id="inspect-shape" disabled></select></label>
      <label for="inspect-weight">Greutate<output id="inspect-weight-value">0%</output></label><input type="range" id="inspect-weight" min="0" max="1" step=".01" value="0" disabled>
      <div class="inspector-live"><span id="inspect-source">Automat · REST</span><span>GREUTĂȚI LIVE</span></div>
      <div class="morph-weights">${WATCH.map(name=>`<label>${name}<meter data-morph="${name}" min="0" max="1" value="0"></meter><output data-weight="${name}">0.00</output></label>`).join("")}</div>
      <button type="button" id="reset-inspection" class="character-reset">Revino la animare</button>
    </section>`;
  view.append(panel);
  let opened=false,visible=false,nextUpdate=0;
  const tabs=[panel.querySelector("#appearance-tab"),panel.querySelector("#inspector-tab")];
  function selectTab(index) {
    tabs.forEach((tab,i)=>{tab.setAttribute("aria-selected",String(i===index));tab.tabIndex=i===index?0:-1;});
    panel.querySelector("#character-appearance").hidden=index!==0;
    panel.querySelector("#character-inspector").hidden=index!==1;
  }
  tabs.forEach((tab,index)=>{
    tab.addEventListener("click",()=>selectTab(index));
    tab.addEventListener("keydown",event=>{
      if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;
      event.preventDefault();const target=event.key==="Home"?0:event.key==="End"?1:1-index;
      selectTab(target);tabs[target].focus();
    });
  });
  function toggle(open) {
    opened=open;panel.hidden=!visible||!opened;
    button.setAttribute("aria-expanded",String(visible&&opened));
    if(!open&&manual.checked)prepareSpeech();
    if(open&&visible)tabs.find(t=>t.tabIndex===0).focus();
  }
  button.addEventListener("click",()=>toggle(!opened));
  panel.querySelector("#close-character-tools").addEventListener("click",()=>{toggle(false);button.focus();});
  panel.addEventListener("keydown",event=>{if(event.key==="Escape"){toggle(false);button.focus();}});
  function applyAppearance() {
    character.setAppearance(settings);stage.setTheme(settings.theme);view.dataset.scene=settings.theme;
    try{localStorage.setItem("character-appearance",JSON.stringify(settings));}catch{/* Optional preference. */}
  }
  function syncAppearance() {
    for(const name of Object.keys(DEFAULTS)) {
      const input=panel.querySelector(`#character-${name}`);
      if(input.type==="checkbox")input.checked=settings[name];else input.value=settings[name];
    }
  }
  for(const name of Object.keys(DEFAULTS)) {
    const input=panel.querySelector(`#character-${name}`);
    input.addEventListener("input",()=>{
      settings[name]=input.type==="checkbox"?input.checked:input.value;applyAppearance();
      if(name==="framing")reframe();
    });
  }
  panel.querySelector("#reset-character-appearance").addEventListener("click",()=>{
    Object.assign(settings,DEFAULTS);syncAppearance();applyAppearance();reframe();
  });
  const manual=panel.querySelector("#inspect-manual"),shape=panel.querySelector("#inspect-shape"),weight=panel.querySelector("#inspect-weight");
  function syncManual() {shape.disabled=weight.disabled=!manual.checked;panel.querySelector("#inspect-weight-value").value=`${Math.round(Number(weight.value)*100)}%`;}
  manual.addEventListener("change",()=>{
    if(manual.checked)interrupt();
    character.setInspection({manual:manual.checked,shape:shape.value,weight:Number(weight.value)});syncManual();
  });
  shape.addEventListener("change",()=>character.setInspection({shape:shape.value}));
  weight.addEventListener("input",()=>{character.setInspection({weight:Number(weight.value)});syncManual();});
  for(const name of ["skeleton","wireframe"])panel.querySelector(`#inspect-${name}`).addEventListener("change",event=>character.setInspection({[name]:event.target.checked}));
  function prepareSpeech() {manual.checked=false;character.setInspection({manual:false});syncManual();}
  panel.querySelector("#reset-inspection").addEventListener("click",()=>{
    prepareSpeech();weight.value=0;syncManual();character.setInspection({skeleton:false,wireframe:false,weight:0});
    panel.querySelector("#inspect-skeleton").checked=panel.querySelector("#inspect-wireframe").checked=false;
  });
  syncAppearance();
  return {
    prepareSpeech,
    modelLoaded() {
      panel.querySelector("#character-model-info").textContent=`${character.humanBoneCount} oase umanoide · ${Object.keys(character.faceMesh.morphTargetDictionary).length} forme faciale`;
      shape.replaceChildren(...character.facialNames.map(name=>new Option(name,name)));
      shape.value="jawOpen";stage.place(character.bounds);
    },
    setVisible(value) {visible=value;button.hidden=!value;panel.hidden=!value||!opened;button.setAttribute("aria-expanded",String(value&&opened));if(!value)prepareSpeech();},
    update(time) {
      if(!visible||panel.hidden||time<nextUpdate||panel.querySelector("#character-inspector").hidden)return;
      nextUpdate=time+100;
      panel.querySelector("#inspect-source").textContent=manual.checked?"Manual":`Automat · ${character.lastViseme||"REST"}`;
      for(const name of WATCH) {
        const value=character.getMorph(name);panel.querySelector(`[data-morph="${name}"]`).value=value;
        panel.querySelector(`[data-weight="${name}"]`).value=value.toFixed(2);
      }
    },
  };
}
