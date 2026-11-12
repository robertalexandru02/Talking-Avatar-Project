import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from spoken_romanian import prepare, short_pieces

class SpokenRomanianTests(unittest.TestCase):
    def test_numbers_abbreviations_and_letters(self):
        self.assertEqual(prepare('LLM și TTS, API, IPA. 140%, 1 ms, 20 ms. nr. 24, et. 3, ap. 12. Personaj 3D.'),
            'el el em și te te es, a pe i, i pe a. 140 la sută, o milisecundă, 20 de milisecunde. numărul 24, etajul 3, apartamentul 12. Personaj trei de.')

    def test_units_have_singular_and_de_where_needed(self):
        self.assertEqual(prepare('1 FPS, 19 FPS, 60 FPS, 101 FPS, 120 FPS.'),
            'un cadru pe secundă, 19 cadre pe secundă, 60 de cadre pe secundă, 101 cadre pe secundă, 120 de cadre pe secundă.')

    def test_expanded_fragments_preserve_every_word(self):
        text=prepare('LLM TTS API '*50)
        pieces=list(short_pieces(text))
        self.assertEqual(' '.join(pieces),' '.join(text.split()))
        self.assertTrue(all(len(piece)<=180 for piece in pieces))

    def test_protect_urls_email_code_identifiers_and_ordinary_words(self):
        text='https://site.ro/API/nr.24?a=140% www.site.ro/TTS ana@API.ro `API nr.24` model_API API_URL app.API /API/test TTS-demo Ollama Raluca'
        self.assertEqual(prepare(text),text)

    def test_diacritics_without_guessing_missing_accents_or_grammar(self):
        self.assertEqual(prepare('Ştiu să-ţi spun bună. Buna. Ce te aduce în plată?'),'Știu să-ți spun bună. Buna. Ce te aduce în plată?')
