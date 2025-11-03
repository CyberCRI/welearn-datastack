import unittest
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.modules import computed_metadata


class TestComputedMetadata(unittest.TestCase):
    def setUp(self):
        self.text_en = "This is a simple test sentence. It is written in English."
        self.text_fr = (
            "Ceci est une phrase de test simple. Elle est écrite en français."
        )
        self.doc_en = WeLearnDocument(
            id=1,
            url="https://example.org/test_en",
            full_content=self.text_en,
            description="A test document in English.",
        )
        self.doc_fr = WeLearnDocument(
            id=2,
            url="https://example.org/test_fr",
            full_content=self.text_fr,
            description="Un document de test en français.",
        )

    def test_remove_punctuation_removes_all_except_apostrophes(self):
        text = "Hello, world! It's a test."
        result = computed_metadata.remove_punctuation(text)
        self.assertEqual("Hello world It's a test", result)

    def test_lexicon_count_counts_words(self):
        text = "Hello world! This is a test."
        self.assertEqual(computed_metadata.lexicon_count(text), 6)

    def test_syllable_count_en(self):
        count = computed_metadata.syllable_count("Hello world", "en")
        self.assertTrue(isinstance(count, int))
        self.assertTrue(count, 2)

    def test_predict_readability_en(self):
        score = computed_metadata.predict_readability(self.text_en, "en")
        self.assertTrue(80.0 <= float(score) <= 100.0)

    def test_predict_duration_en(self):
        duration = computed_metadata.predict_duration(self.text_en, "en")
        self.assertTrue(duration.isdigit())
        self.assertEqual(duration, "2")

    def test_identify_document_language_sets_lang_and_details(self):
        doc = WeLearnDocument(
            id=3,
            url="https://example.org/test_lang",
            full_content=self.text_en,
            description="A test document in English.",
            details={},
        )
        result = computed_metadata.identify_document_language(doc)
        self.assertEqual(result.lang, "en")
        self.assertIn("content_and_description_lang", result.details)
        self.assertFalse(
            result.details["content_and_description_lang"]["are_different"]
        )

    def test_identify_document_language_detects_difference(self):
        doc = WeLearnDocument(
            id=4,
            url="https://example.org/test_diff",
            full_content=self.text_en,
            description=self.text_fr,
            details={},
        )
        result = computed_metadata.identify_document_language(doc)
        self.assertEqual(result.lang, "en")
        self.assertTrue(result.details["content_and_description_lang"]["are_different"])

    def test_lexicon_count(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(computed_metadata.lexicon_count(text), 7)

    def test_sentence_count(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(computed_metadata.sentence_count(text), 1)

    def test_avg_sentence_length(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(computed_metadata.avg_sentence_length(text), 7.0)

    def test_syllable_count(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(computed_metadata.syllable_count(text, "en"), 10)

    def test_avg_syllables_per_word(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            computed_metadata.avg_syllables_per_word(text, "en"),
            1.4285714285714286,
        )

    def test_predict_readability(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            computed_metadata.predict_readability(text, "en"),
            "78.87",
        )

    def test_predict_duration(self):
        text = "Hello, World! Isn't it a beautiful day?"
        self.assertEqual(
            computed_metadata.predict_duration(text, "en"),
            "2",
        )
