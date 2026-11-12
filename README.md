# Talking Avatar — laborator de conversație 3D

Aplicație web care combină un LLM local cu voce și animație procedurală în Three.js.
**Ollama → text în streaming → Piper + viseme → audio și animație 3D.**

## Funcționalități

- Conversație cu Gemma3:4b prin Ollama, în română și engleză.
- Voci: Raluca pentru personaj, Liana High cu efect robotic pentru roi și Lessac pentru engleză.
- Microfon cu Whisper local; transcrierea poate fi verificată înainte de trimitere.
- Personaj VRM cu lip-sync, clipire și privire spre cursor; alternativ, roi de particule interactiv.
- Personalizare, trei ambianțe 3D și laborator grafic pentru schelet, wireframe și forme faciale.
- Oprire, reascultare, copiere și exportul conversației în TXT.

## Instalare și pornire

### Varianta simplificată

1. Instalează [Python 3.10–3.12](https://www.python.org/downloads/) și
   [Ollama](https://ollama.com/). La instalarea Python pe Windows, bifează **Add Python to PATH**.
2. Descarcă proiectul prin **Code → Download ZIP** și dezarhivează-l complet.
3. Pe **Windows**, deschide **`start.bat`** prin dublu-click.

Pe **Linux/macOS**, deschide terminalul în folderul proiectului și rulează:

```sh
python3 start.py
```

Launcherul pregătește mediul Python, instalează dependențele, pornește Ollama
local dacă este necesar, descarcă modelele lipsă și deschide **http://localhost:8000**.
Prima instalare descarcă mai mulți GB și poate dura; păstrează conexiunea la internet.
Modelul microfonului afișează progresul descărcării și nu necesită cont sau token Hugging Face.
La pornirile următoare, folosește același launcher: instalarea existentă este reutilizată.

Păstrează terminalul deschis cât folosești laboratorul. **Ctrl+C** oprește serverul.
Permite accesul la microfon în browser. Pregătire fără pornire: `python start.py --setup-only`.

### Varianta manuală

Instalează Python 3.10–3.12 și Ollama, apoi dezarhivează proiectul. Lasă Ollama pornit;
dacă serviciul nu rulează, execută `ollama serve` într-un terminal separat.
Din folderul proiectului, rulează în PowerShell:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
ollama pull gemma3:4b
python backend/download_voices.py
python backend/download_asr.py
python -m uvicorn main:app --app-dir backend --reload
```

Pe Linux/macOS creează mediul cu `python3 -m venv backend/.venv` și activează-l cu
`source backend/.venv/bin/activate`; continuă cu comenzile de instalare de mai sus.
Dacă PowerShell blochează activarea, folosește CMD și `backend\.venv\Scripts\activate.bat`.

Deschide **http://localhost:8000**. La următoarele porniri manuale ai nevoie doar de
Ollama pornit, activarea mediului și ultima comandă. **Ctrl+C** oprește serverul.

### Configurare

Configurare opțională: copiază `backend/.env.example` în `backend/.env`, ajustează
valorile și repornește launcherul. Fișierul existent nu este suprascris.
`PIPER_LIANA_QUALITY=medium` oferă sinteză mai rapidă.

### Verificarea instalării simplificate

1. Oprește laboratorul și extrage arhiva într-un folder separat, de exemplu `Desktop/Test Avatar`.
2. În copia extrasă, pornește `start.bat`. Prima rulare trebuie să creeze mediul
   `backend/.venv` și să descarce vocile și modelul microfonului.
3. După deschiderea browserului, trimite un mesaj, ascultă răspunsul, verifică gura
   personajului, comută pe roi și încearcă microfonul.
4. Oprește cu **Ctrl+C** și pornește din nou: instalarea și modelele existente trebuie reutilizate.

Pe același calculator, modelul din Ollama este comun și va fi reutilizat. Pentru a
verifica și descărcarea lui inițială, testează pe alt calculator fără modelul instalat.

## Structură și verificare

```text
start.bat         Instalare și pornire pe Windows
start.py          Launcher pentru instalare și pornire
backend/          Server, LLM, TTS, microfon și scripturi de instalare
frontend/         Interfață, scenă 3D, avatar inclus și prezentarea proiectului
tests/unit/       Teste automate fără servicii externe
tests/smoke/      Verificări de browser și probe cu modelele locale
```

Cu mediul Python activ: `python -B -m unittest discover -s tests/unit -v`.
Pentru testele de browser instalează `python -m pip install -r tests/requirements.txt`
și `python -m playwright install chromium`.

## Resurse

Textul, vocea și transcrierea sunt procesate local. Interfața încarcă Three.js de pe CDN.

Vocile românești [Raluca/Sanda](https://huggingface.co/eduardem/piper-tts-romanian) și
[Liana](https://huggingface.co/eduardem/piper-liana-romanian), de eduardem, au licență
**CC BY-NC 4.0**.
