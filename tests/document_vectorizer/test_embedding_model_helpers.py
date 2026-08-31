import os
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import numpy
from welearn_database.data.models import (
    Corpus,
    EmbeddingModel,
    WeLearnDocument,
)

from welearn_datastack.modules.embedding_model_helpers import (
    _split_by_word_respecting_sent_boundary,
    create_content_slices,
)
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)


class TestEmbeddingHelper(TestCase):
    def setUp(self) -> None:
        get_sub_environ_according_prefix.cache_clear()
        os.environ["ST_BACKEND"] = "torch"

    def tearDown(self) -> None:
        os.environ.clear()

    @patch("welearn_datastack.modules.embedding_model_helpers." "_compute_embeddings")
    @patch("welearn_datastack.modules.embedding_model_helpers." "load_embedding_model")
    @patch(
        "welearn_datastack.modules.embedding_model_helpers."
        "_split_by_word_respecting_sent_boundary"
    )
    def test_create_content_slices(
        self,
        mock_split_by_sent_boundary,
        mock_load_embedding_model,
        mock_compute_embeddings,
    ):
        os.environ["MODELS_PATH_ROOT"] = "test"

        embedding_1 = numpy.random.uniform(low=-1, high=1, size=(50,))
        embedding_2 = numpy.random.uniform(low=-1, high=1, size=(50,))

        fake_model = MagicMock()
        fake_tokenizer = MagicMock()
        fake_tokenizer.model_max_length = 5
        mock_load_embedding_model.return_value = (fake_model, fake_tokenizer)
        mock_split_by_sent_boundary.return_value = [
            "This is a sentence.",
            "This is another sentence.",
        ]
        mock_compute_embeddings.return_value = numpy.array([embedding_1, embedding_2])

        test_document = WeLearnDocument(
            id=uuid.uuid4(),
            title="test",
            url="https://example.org/test",
            lang="en",
            full_content="This is a sentence. This is another sentence.",
            corpus=Corpus(
                id=uuid.uuid4(),
                source_name="test",
                is_fix=True,
            ),
            description="test",
            details={},
        )

        emb_m_id = uuid.uuid4()
        emb_model = EmbeddingModel(
            id=emb_m_id,
            title="test_en",
            lang="en",
        )

        slices = create_content_slices(
            test_document,
            embedding_model_name=emb_model.title,
            embedding_model_id=emb_m_id,
        )

        ret_emb0 = numpy.frombuffer(slices[0].embedding).all()
        ret_emb1 = numpy.frombuffer(slices[1].embedding).all()

        self.assertEqual(2, len(slices))
        self.assertEqual("This is a sentence.", slices[0].body)
        self.assertEqual(emb_m_id, slices[0].embedding_model_id)
        self.assertEqual(embedding_1.all(), ret_emb0)
        self.assertEqual("This is another sentence.", slices[1].body)
        self.assertEqual(embedding_2.all(), ret_emb1)
        self.assertEqual(emb_m_id, slices[1].embedding_model_id)
        mock_load_embedding_model.assert_called_once()
        mock_compute_embeddings.assert_called_once_with(
            fake_model,
            fake_tokenizer,
            ["This is a sentence.", "This is another sentence."],
        )

    def test__split_by_word_respecting_sent_boundary(self):
        """
        Test that the text is correctly split by word
        respecting sentence boundary
        """
        text = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Sed do eiusmod tempor incididunt ut labore et dolore "
            "magna aliqua."
        )
        sents = _split_by_word_respecting_sent_boundary(
            slice_length=4,
            document_content=text,
            document_lang="en",
        )

        self.assertEqual(len(sents), 2)
        self.assertEqual(sents[0], "Lorem ipsum dolor...")
        self.assertEqual(sents[1], "Sed do eiusmod...")
