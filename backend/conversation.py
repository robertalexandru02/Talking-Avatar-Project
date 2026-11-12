"""Exact social openings only; substantive requests always reach the LLM."""
import re
import unicodedata

def opening_reply(history, lang):
    if lang != 'ro' or not history or history[-1].get('role') != 'user':
        return None
    text=unicodedata.normalize('NFKD',history[-1].get('content','').lower())
    text=''.join(c for c in text if not unicodedata.combining(c))
    text=re.sub(r'\s+',' ',text).strip().strip(' .!?…')
    greetings={'buna':'Bună!', 'salut':'Salut!', 'buna ziua':'Bună ziua!',
               'buna dimineata':'Bună dimineața!', 'buna seara':'Bună seara!'}
    if text in greetings:
        return greetings[text]
    # Full matches avoid swallowing messages such as "Ce faci cu visemele?".
    match=re.fullmatch(r'(?:(buna|salut)[!,. ]+)?(ce (?:mai )?faci|cum esti|cum te simti)(?: astazi| azi)?',text)
    if match:
        prefix=(greetings[match[1]]+' ') if match[1] else ''
        return prefix+'Sunt aici și te ascult.'
    return None
