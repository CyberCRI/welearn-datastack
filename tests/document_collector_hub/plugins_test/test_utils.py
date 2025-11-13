import unittest

import welearn_datastack.modules.computed_metadata
import welearn_datastack.utils_.scraping_utils
import welearn_datastack.utils_.text_stat_utils


class TestUtils(unittest.TestCase):
    def test_remove_punctuation(self):
        text_w_punctuation = "Hello, World! Isn't it a beautiful day?"
        text_wo_punctuation = "Hello World Isn't it a beautiful day"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.remove_punctuation(
                text_w_punctuation
            ),
            text_wo_punctuation,
        )

    def test_lexicon_count(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.lexicon_count(text), 7
        )

    def test_sentence_count(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.sentence_count(text), 1
        )

    def test_avg_sentence_length(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.avg_sentence_length(text), 7.0
        )

    def test_syllable_count(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.syllable_count(text, "en"), 10
        )

    def test_avg_syllables_per_word(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.avg_syllables_per_word(
                text, "en"
            ),
            1.4285714285714286,
        )

    def test_predict_readability(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.predict_readability(text, "en"),
            "78.87",
        )

    def test_predict_duration(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            welearn_datastack.modules.computed_metadata.predict_duration(text, "en"),
            "2",
        )

    def test_clean_text(self):
        html_text = "<p>Hello, World! Isn't it a beautiful  day?</p>"
        self.assertEqual(
            welearn_datastack.utils_.scraping_utils.clean_text(html_text),
            "Hello, World! Isn't it a beautiful day?",
        )
