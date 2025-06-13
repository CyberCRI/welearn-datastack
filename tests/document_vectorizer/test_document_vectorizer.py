import csv
import os
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import (
    Base,
    Category,
    Corpus,
    CorpusEmbeddingModel,
    DocumentSlice,
    EmbeddingModel,
    ProcessState,
    WeLearnDocument,
)
from welearn_datastack.data.enumerations import Step
from welearn_datastack.nodes_workflow.DocumentVectorizer import document_vectorizer
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)


class TestDocumentVecto(unittest.TestCase):
    def setUp(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_NAME_PREFIX"] = "EMBEDDING_MODEL"
        os.environ["EMBEDDING_MODEL_FR"] = "test_fr"
        os.environ["EMBEDDING_MODEL_EN"] = "test_en"
        os.environ["MODELS_PATH_ROOT"] = "test"

        os.environ["PG_DRIVER"] = "sqlite"
        os.environ["PG_USER"] = ""
        os.environ["PG_PASSWORD"] = ""  # nosec
        os.environ["PG_HOST"] = ""
        os.environ["PG_DB"] = ":memory:"

        self.engine = create_engine("sqlite://")
        s_maker = sessionmaker(self.engine)
        handle_schema_with_sqlite(self.engine)

        self.test_session = s_maker()
        Base.metadata.create_all(self.test_session.get_bind())

        self.category_name = "category_test0"

        self.category_id = uuid.uuid4()

        self.category = Category(id=self.category_id, title=self.category_name)

        self.test_session.add(self.category)

        corpus_source_name = "test_corpus"

        self.embedding_model = EmbeddingModel(
            id=uuid.uuid4(),
            title="test_en",
            lang="en",
        )

        self.test_session.add(self.embedding_model)

        self.corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
        )

        self.test_session.add(self.corpus_test)

        self.corpus_embedding_model_id = uuid.uuid4()
        self.embedding_model_corpus = CorpusEmbeddingModel(
            corpus_id=self.corpus_test.id,
            embedding_model_id=self.embedding_model.id,
        )

        self.test_session.add(self.embedding_model_corpus)

        self.test_session.commit()

        self.path_test_input = Path(__file__).parent.parent / "resources" / "input"
        self.path_test_input.mkdir(parents=True, exist_ok=True)

        os.environ["ARTIFACT_ROOT"] = self.path_test_input.parent.as_posix()

    def tearDown(self):
        self.test_session.close()
        del self.test_session

    @patch(
        "welearn_datastack.nodes_workflow.DocumentVectorizer.document_vectorizer.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentVectorizer.document_vectorizer.create_content_slices"
    )
    def test_document_vectorizer(
        self, mock_create_content_slices, mock_create_db_session
    ):
        mock_create_db_session.return_value = self.test_session

        doc_id = uuid.uuid4()

        with (self.path_test_input / "batch_ids.csv").open("w") as f:
            writer = csv.writer(f)
            writer.writerow([doc_id])

        emb0 = numpy.random.uniform(low=-1, high=1, size=(50,))
        emb1 = numpy.random.uniform(low=-1, high=1, size=(50,))

        mock_slices = [
            DocumentSlice(
                id=uuid.uuid4(),
                body="This is a sentence.",
                document_id=doc_id,
                order_sequence=0,
                embedding=emb0.tobytes(),
                embedding_model_id=uuid.uuid4(),
                embedding_model_name="test_model",
            ),
            DocumentSlice(
                id=uuid.uuid4(),
                body="This is another sentence.",
                document_id=doc_id,
                order_sequence=1,
                embedding=emb1.tobytes(),
                embedding_model_id=uuid.uuid4(),
                embedding_model_name="test_model",
            ),
        ]

        doc = WeLearnDocument(
            id=doc_id,
            title="test",
            url="https://www.example.org/wiki/Randomness",
            lang="en",
            full_content="This is a sentence. This is another sentence.",
            corpus=self.corpus_test,
            description="test",
            details={},
        )

        state = ProcessState(
            id=uuid.uuid4(),
            document_id=doc_id,
            title=Step.DOCUMENT_SCRAPED.value,
            created_at=datetime.now() - timedelta(seconds=1),
        )

        self.test_session.add(doc)
        self.test_session.add(state)
        self.test_session.commit()

        mock_create_content_slices.return_value = mock_slices

        document_vectorizer.main()

        doc_slices = (
            self.test_session.query(DocumentSlice)
            .filter(DocumentSlice.document_id == doc_id)
            .all()
        )

        ret_emb0 = numpy.frombuffer(doc_slices[0].embedding).all()
        ret_emb1 = numpy.frombuffer(doc_slices[1].embedding).all()

        self.assertEqual(2, len(doc_slices))
        self.assertEqual("This is a sentence.", doc_slices[0].body)
        self.assertEqual(emb0.all(), ret_emb0)
        self.assertEqual("This is another sentence.", doc_slices[1].body)
        self.assertEqual(emb1.all(), ret_emb1)

        states = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == doc_id)
            .all()
        )

        most_recent_state = max(states, key=lambda x: x.created_at.timestamp())

        self.assertEqual(Step.DOCUMENT_VECTORIZED.value, most_recent_state.title)
