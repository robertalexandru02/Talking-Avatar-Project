"""Small, explicit local source of application facts, used only for project questions."""
import re
import unicodedata

def related(history):
    users=[message.get("content","") for message in history if message.get("role")=="user"][-3:]
    text=" ".join(users).lower()
    text="".join(c for c in unicodedata.normalize("NFKD",text) if not unicodedata.combining(c))
    return bool(re.search(r"talking avatar|acest(?:ui)? proiect|proiectul (?:asta|nostru|meu)|aceasta aplicatie|aplicatia (?:asta|noastra)|this (?:app|project)|three\.?js|blendshape|morph target|visem|lip[ -]?sync|piper|arkit|viverse",text))

def facts(model,lang):
    if lang=="en":
        return (
            f"Verified application facts: the active local language model is {model}, served by Ollama. "
            "Ollama streams answer text. Piper turns sentence/clause text into WAV audio and timed IPA phonemes. "
            "The backend maps phonemes to visemes. Three.js uses the audio clock to animate ARKit morph targets "
            "on a VIVERSE VRM 0.0 character (glTF, 60 facial targets including 52 ARKit). "
            "Interpolation smooths transitions. The LLM does not generate facial muscle commands. "
            "Romanian voices: Raluca for the character, Liana with a robot effect for particles; English uses Lessac. "
            "Whisper small transcribes the microphone locally; the user reviews text before sending. "
            "The graphic lab shows bones, wireframe and manual morph weights. The particle swarm is an alternative, "
            "not facial lip-sync. This is the web variant, not Unity or Unreal. Alignment and reasoning are imperfect."
        )
    return (
        f"Date verificate despre aplicație: modelul lingvistic local activ este {model}, servit prin Ollama. "
        "Ollama transmite text în streaming. Piper transformă propoziții/clauze în WAV și foneme IPA temporizate. "
        "Backendul mapează fonemele în viseme. Three.js folosește ceasul audio pentru morph targets ARKit pe "
        "un personaj VIVERSE VRM 0.0, bazat pe glTF, cu 60 de forme faciale, inclusiv 52 ARKit. "
        "Interpolarea netezește tranzițiile. LLM-ul nu generează comenzi pentru mușchii feței. "
        "Vocile românești sunt Raluca pentru personaj și Liana cu efect robot pentru roi; engleza folosește Lessac. "
        "Whisper small transcrie microfonul local; utilizatorul verifică textul înainte de trimitere. "
        "Laboratorul arată scheletul, rețeaua de poligoane și greutățile faciale manuale. "
        "Roiul este o alternativă artistică, fără lip-sync facial. Varianta aleasă este web, nu Unity sau Unreal. "
        "Alinierea și raționamentul nu sunt perfecte."
    )
