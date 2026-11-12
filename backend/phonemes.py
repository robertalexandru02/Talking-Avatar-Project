"""Cuvânt -> secvență de (grupă visemă, durată relativă).

Română  : silabificare + reguli RegEx aplicate pe silabe (limba e puternic fonetică)
Engleză : g2p_en (ARPAbet) -> grupe de viseme
"""
import re

# Grupele din matricea de mapare a proiectului
A_O = "A_O"        # A, AH, O, UH   -> Jaw_Open + Mouth_Funnel
E_I = "E_I"        # E, EH, AE, I   -> Mouth_Smile + Jaw_Open (mic)
BMP = "BMP"        # B, M, P        -> Mouth_Close
FV = "FV"          # F, V           -> Mouth_Shrug_Lower
W_OO = "W_OO"      # W, OO          -> Mouth_Pucker
LDTNS = "LDTNS"    # L, D, T, N, S (+ restul consoanelor) -> Jaw_Open (min) + Mouth_Stretch
REST = "REST"      # liniște

# durate relative (se scalează apoi la durata reală a audio-ului)
DUR = {A_O: 1.0, E_I: 0.9, W_OO: 0.9, BMP: 0.6, FV: 0.7, LDTNS: 0.6}

# ---------------------------------------------------------------- ROMÂNĂ
RO_VOWELS = "aeiouăâî"
RO_CLUSTERS = {"bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl", "pr", "tr", "vr"}

RO_GROUP = {
    **dict.fromkeys("aăo", A_O),
    **dict.fromkeys("eiâîĭ", E_I),
    **dict.fromkeys("uw", W_OO),
    **dict.fromkeys("bmp", BMP),
    **dict.fromkeys("fv", FV),
}  # orice altceva -> LDTNS

# Reguli fonetice RegEx, aplicate în ordine pe fiecare silabă
RO_RULES = [
    (r"ch(?=[ei])", "k"),   # che, chi -> k (h e mut)
    (r"gh(?=[ei])", "g"),   # ghe, ghi -> g
    (r"c(?=[ei])", "C"),    # ce, ci   -> tʃ
    (r"g(?=[ei])", "J"),    # ge, gi   -> dʒ
    (r"ș", "S"),            # ʃ
    (r"ț", "T"),            # ts
    (r"x", "ks"),
]


def syllabify_ro(w: str):
    """Silabificare simplificată: grupurile vocalice sunt nuclee; consoanele dintre
    nuclee se împart după regulile V-CV, VC-CV și grupuri muta cum liquida."""
    parts = re.findall(f"[{RO_VOWELS}]+|[^{RO_VOWELS}]+", w)
    sylls, onset, i = [], "", 0
    if parts and parts[0][0] not in RO_VOWELS:
        onset, i = parts[0], 1
    while i < len(parts):
        nucleus = parts[i]
        cons = parts[i + 1] if i + 1 < len(parts) else ""
        if i + 2 >= len(parts):                   # ultima silabă: restul e coda
            sylls.append(onset + nucleus + cons)
            break
        units = re.findall(r"ch|gh|.", cons)      # ch/gh sunt inseparabile
        if len(units) == 1:
            coda, nxt = [], units
        elif len(units) == 2 and "".join(units) in RO_CLUSTERS:
            coda, nxt = [], units
        elif len(units) == 2:
            coda, nxt = units[:1], units[1:]
        elif "".join(units[-2:]) in RO_CLUSTERS:
            coda, nxt = units[:-2], units[-2:]
        else:
            coda, nxt = units[:-1], units[-1:]
        sylls.append(onset + nucleus + "".join(coda))
        onset = "".join(nxt)
        i += 2
    return sylls or [w]


def phonemes_ro(word: str):
    w = word.lower().replace("ş", "ș").replace("ţ", "ț")
    sylls = syllabify_ro(w)
    out = []
    for n, syl in enumerate(sylls):
        for pat, rep in RO_RULES:
            syl = re.sub(pat, rep, syl)
        if n == len(sylls) - 1 and len(sylls) > 1:      # -i final după consoană: foarte scurt
            syl = re.sub(r"(?<=[^aeiouăâî])i$", "ĭ", syl)
        for ch in syl:
            g = RO_GROUP.get(ch, LDTNS)
            out.append((g, 0.4 if ch == "ĭ" else DUR[g]))
    return out


# ---------------------------------------------------------------- ENGLEZĂ
ARPA_GROUP = {
    **dict.fromkeys(["AA", "AH", "AO", "AW", "OW", "OY", "UH", "ER"], A_O),
    **dict.fromkeys(["AE", "EH", "IH", "IY", "EY", "AY"], E_I),
    **dict.fromkeys(["UW", "W"], W_OO),
    **dict.fromkeys(["B", "M", "P"], BMP),
    **dict.fromkeys(["F", "V"], FV),
}

_g2p, _g2p_failed = None, False


def _get_g2p():
    global _g2p, _g2p_failed
    if _g2p is None and not _g2p_failed:
        try:
            import nltk
            resources = {"averaged_perceptron_tagger_eng": "taggers/averaged_perceptron_tagger_eng",
                         "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
                         "cmudict": "corpora/cmudict"}
            for pkg, resource in resources.items():
                try:
                    nltk.data.find(resource)
                except LookupError:
                    if not nltk.download(pkg, quiet=True):
                        raise RuntimeError(f"Resursa NLTK {pkg} nu este disponibilă.")
            from g2p_en import G2p
            _g2p = G2p()
        except Exception as e:  # noqa: BLE001
            _g2p_failed = True
            print(f"[phonemes] g2p_en indisponibil ({e}); folosesc reguli pe litere pentru engleză")
    return _g2p


LETTER_GROUP = {
    **dict.fromkeys("ao", A_O),
    **dict.fromkeys("eiy", E_I),
    **dict.fromkeys("uw", W_OO),
    **dict.fromkeys("bmp", BMP),
    **dict.fromkeys("fv", FV),
}


def phonemes_letters(word: str):
    """Fallback simplu pe litere."""
    out = []
    for c in word.lower():
        if c.isalpha():
            g = LETTER_GROUP.get(c, LDTNS)
            out.append((g, DUR[g]))
    return out


def phonemes_en(word: str):
    g2p = _get_g2p()
    if g2p is None:
        return phonemes_letters(word)
    out = []
    for p in g2p(word):
        p = re.sub(r"\d", "", p)                 # scoate accentul (AH0 -> AH)
        if not (p.isalpha() and p.isupper()):
            continue
        g = ARPA_GROUP.get(p, LDTNS)
        out.append((g, DUR[g]))
    return out or phonemes_letters(word)


# ---------------------------------------------------------------- API
def word_to_visemes(word: str, lang: str = "ro"):
    alpha = re.sub(r"[\W\d_]+", "", word)
    digits = len(re.findall(r"\d", word))
    if not alpha:
        ph = []
    elif lang == "en":
        ph = phonemes_en(alpha)
    else:
        ph = phonemes_ro(alpha)
    return ph + [(LDTNS, DUR[LDTNS])] * digits


def warmup():
    _get_g2p()
