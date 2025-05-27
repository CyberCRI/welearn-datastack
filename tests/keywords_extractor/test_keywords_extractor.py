import unittest
from unittest.mock import MagicMock, patch

from welearn_datastack.data.db_models import WeLearnDocument
from welearn_datastack.modules.keywords_extractor import extract_keywords


class TestKeywordsExtractor(unittest.TestCase):

    @patch("welearn_datastack.modules.keywords_extractor.load_embedding_model")
    @patch("welearn_datastack.modules.keywords_extractor.generate_ml_models_path")
    @patch("welearn_datastack.modules.keywords_extractor.KeyBERT")
    @patch(
        "welearn_datastack.modules.keywords_extractor.get_document_embedding_model_name_from_lang"
    )
    def test_extract_keywords(
        self,
        mock_get_model_name,
        mock_KeyBERT,
        mock_generate_ml_models_path,
        mock_load_embedding_model,
    ):
        # Mock the return values
        mock_generate_ml_models_path.return_value.as_posix.return_value = "mock_path"
        mock_load_embedding_model.return_value = "mock_embedding_model"
        mock_nlp_model = MagicMock()
        mock_nlp_model.return_value = MagicMock()
        mock_kw_model = mock_KeyBERT.return_value
        mock_kw_model.extract_keywords.return_value = [
            ("keyword1", 0.6),
            ("keyword2", 0.4),
        ]
        mock_get_model_name.return_value = "test_en_model"

        # Create a mock document
        mock_document = WeLearnDocument(
            id="test_id",
            url="https://example.org",
            corpus_id="test_corpus_id",
            title="test",
            lang="en",
            full_content="test",
            description="This is a test description.",
            details={"test": "test"},
            trace=1,
        )

        # Call the function
        keywords = extract_keywords(mock_document)

        # Assertions
        mock_generate_ml_models_path.assert_called_once()
        mock_load_embedding_model.assert_called_once_with("mock_path")
        mock_kw_model.extract_keywords.assert_called_once()
        self.assertEqual(keywords, ["keyword1"])
