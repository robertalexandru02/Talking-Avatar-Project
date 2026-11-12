import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import phonemes
import main


class PhonemeTests(unittest.TestCase):
    def test_romanian_syllables_and_diacritics(self):
        self.assertEqual(phonemes.syllabify_ro("carte"), ["car", "te"])
        self.assertEqual(phonemes.phonemes_ro("șarpe"), phonemes.phonemes_ro("şarpe"))
        self.assertEqual(phonemes.word_to_visemes("mama", "ro")[0][0], "BMP")
        self.assertTrue(all(duration > 0 for _, duration in phonemes.word_to_visemes("bună", "ro")))

    def test_english_arpabet_mapping(self):
        with patch.object(phonemes, "_get_g2p", return_value=lambda word: ["F", "IH1", "SH"]):
            self.assertEqual([group for group, _ in phonemes.word_to_visemes("fish", "en")], ["FV", "E_I", "LDTNS"])

    def test_english_fallback_is_explicitly_available(self):
        with patch.object(phonemes, "_get_g2p", return_value=None):
            self.assertEqual(phonemes.phonemes_en("fish"), phonemes.phonemes_letters("fish"))

    def test_viseme_timeline_fits_real_audio_window(self):
        timeline = main.build_timeline(phonemes.word_to_visemes("mama", "ro"), 80, 1280)
        self.assertEqual(timeline[0]["t"], 80)
        self.assertAlmostEqual(timeline[-1]["t"] + timeline[-1]["d"], 1280, delta=1)
        self.assertTrue(all(x["d"] > 0 for x in timeline))
        self.assertEqual([x["t"] for x in timeline], sorted(x["t"] for x in timeline))


if __name__ == "__main__":
    unittest.main()
