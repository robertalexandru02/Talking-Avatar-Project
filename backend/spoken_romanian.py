"""Conservative spoken forms for Romanian TTS; never edits conversation/history."""
import re
import unicodedata

_PROTECTED = re.compile(r'https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|`[^`]*`',re.I)
_INITIALISMS = {'LLM':'el el em','TTS':'te te es','API':'a pe i','IPA':'i pe a',
                'CPU':'ce pe u','GPU':'ghe pe u','VRM':'ve er em','GLB':'ghe el be',
                'GLTF':'ghe el te ef','FPS':'cadre pe secundă'}
_LETTERS = re.compile(r'(?<![\w./\\-])(?:'+ '|'.join(_INITIALISMS)+r')(?![\w/\\-]|\.\w)')

def _expand(text):
    # Only numeric contexts: "nr." in a URL or identifier must stay intact.
    for short,full in [('nr','numărul'),('et','etajul'),('ap','apartamentul')]:
        text=re.sub(r'(?<!\w)'+short+r'\.\s*(?=\d)',full+' ',text,flags=re.I)
    text=re.sub(r'(?<!\w)aprox\.(?=\s)', 'aproximativ',text,flags=re.I)
    def unit(match, singular, plural, one):
        number=match[1]
        if number=='1':return one+' '+singular
        needs_de=number.isdigit() and int(number)>=20 and (int(number)%100==0 or int(number)%100>=20)
        return number+(' de ' if needs_de else ' ')+plural
    text=re.sub(r'\b(\d+(?:[,.]\d+)?)\s*FPS\b',
        lambda m:unit(m,'cadru pe secundă','cadre pe secundă','un'),text)
    text=_LETTERS.sub(lambda m:_INITIALISMS[m[0]],text)
    text=re.sub(r'(?<=\d)\s*%', ' la sută',text)
    text=re.sub(r'\b(\d+(?:[,.]\d+)?)\s*ms\b',
        lambda m:unit(m,'milisecundă','milisecunde','o'),text)
    text=re.sub(r'(?<![\w./\\-])3D(?![\w/\\-]|\.\w)','trei de',text)
    return text

def prepare(text):
    text=unicodedata.normalize('NFC',text).translate(str.maketrans('şţŞŢ','șțȘȚ'))
    parts=[];cursor=0
    for match in _PROTECTED.finditer(text):
        parts.extend([_expand(text[cursor:match.start()]),match[0]])
        cursor=match.end()
    parts.append(_expand(text[cursor:]))
    return ''.join(parts)

def short_pieces(text, limit=180):
    """Bound expanded text on word boundaries; a single long token stays intact."""
    current=[];size=0
    for word in text.split():
        if current and size+1+len(word)>limit:
            yield ' '.join(current)
            current=[];size=0
        current.append(word);size+=len(word)+(1 if len(current)>1 else 0)
        if word.rstrip('\"”»)]')[-1:] in '.!?…' and word.lower() not in {'dr.','prof.','dl.','dna.','etc.'}:
            yield ' '.join(current)
            current=[];size=0
    if current:yield ' '.join(current)
