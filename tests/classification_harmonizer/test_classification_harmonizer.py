import os
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import Base, Corpus, WeLearnDocument, ProcessState, DocumentSlice, Sdg
from welearn_datastack.data.enumerations import Step
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)
from welearn_datastack.nodes_workflow.ClassficationHarmonizer import classification_harmonizer

class TestClassficationHarmonizer(unittest.TestCase):
    def setUp(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["PG_DRIVER"] = "sqlite"
        os.environ["PG_USER"] = ""
        os.environ["PG_PASSWORD"] = ""  # nosec
        os.environ["PG_HOST"] = ""
        os.environ["PG_DB"] = ":memory:"


        self.engine = create_engine("sqlite://")
        handle_schema_with_sqlite(self.engine)

        s_maker = sessionmaker(self.engine)
        self.test_session = s_maker()
        Base.metadata.create_all(self.test_session.get_bind())


        corpus_source_name = "corpus"
        self.corpus_id = uuid.uuid4()

        self.corpus_test = Corpus(
            id=self.corpus_id,
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
        )
        self.test_session.add(self.corpus_test)
        self.test_session.commit()

    def tearDown(self):
        self.test_session.close()
        del self.test_session

    @patch("welearn_datastack.nodes_workflow.ClassficationHarmonizer.bi_classify_slices")
    def test_classification_harmonizer_with_sdgs(self, mock_bi_classifier):
        doc_id = uuid.uuid4()
        external_sdgs = [14, 15]

        mock_bi_classifier.return_value = True

        doc = WeLearnDocument(
            id=doc_id,
            title="test",
            url="https://www.example.org/wiki/Randomness",
            lang="en",
            full_content="This is a sentence. This is another sentence.",
            corpus=self.corpus_test,
            description="test",
            details={'external_sdg': external_sdgs},
        )

        states = [
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_SCRAPED.value,
                created_at=datetime.now() - timedelta(seconds=3),
                operation_order=0,
            ),
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_VECTORIZED.value,
                operation_order=1,
                created_at=datetime.now() - timedelta(seconds=2),
            ),
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_EXTERNALLY_CLASSIFIED.value,
                operation_order=2,
                created_at=datetime.now() - timedelta(seconds=1),
            ),
        ]

        self.slice_id0 = uuid.uuid4()
        self.slice_id1 = uuid.uuid4()
        self.emb0 = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )
        self.emb1 = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )
        self.slice_0 = DocumentSlice(
            id=self.slice_id0,
            body="This is a sentence.",
            document_id=doc_id,
            order_sequence=0,
            embedding=self.emb0.tobytes(),
            embedding_model_name="embmodel",
            embedding_model_id=uuid.uuid4(),
        )
        self.slice_1 = DocumentSlice(
            id=self.slice_id1,
            body="This is another sentence.",
            document_id=doc_id,
            order_sequence=1,
            embedding=self.emb1.tobytes(),
            embedding_model_name="embmodel",
            embedding_model_id=uuid.uuid4(),
        )

        self.test_session.add(doc)
        self.test_session.add_all(states)
        self.test_session.add(self.slice_0)
        self.test_session.add(self.slice_1)
        self.test_session.commit()

        classification_harmonizer.main()

        states = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == doc_id)
            .all()
        )

        most_recent_state = max(states, key=lambda x: x.created_at.timestamp())

        self.assertEqual(Step.DOCUMENT_CLASSIFIED_SDG.value, most_recent_state.title)

        for s_id in [self.slice_id0, self.slice_id1]:
            sdgs = (
                self.test_session.query(Sdg)
                .filter(Sdg.slice_id == s_id)
                .all()
            )
            self.assertListEqual([s.sdg_number for s in sdgs], external_sdgs)


    @patch("welearn_datastack.nodes_workflow.ClassficationHarmonizer.bi_classify_slices")
    def test_classification_harmonizer_without_sdgs(self, mock_bi_classifier):
        doc_id = uuid.uuid4()
        external_sdgs = []

        mock_bi_classifier.return_value = True

        doc = WeLearnDocument(
            id=doc_id,
            title="test",
            url="https://www.example.org/wiki/Randomness",
            lang="en",
            full_content="This is a sentence. This is another sentence.",
            corpus=self.corpus_test,
            description="test",
            details={'external_sdg': external_sdgs},
        )

        states = [
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_SCRAPED.value,
                created_at=datetime.now() - timedelta(seconds=3),
                operation_order=0,
            ),
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_VECTORIZED.value,
                operation_order=1,
                created_at=datetime.now() - timedelta(seconds=2),
            ),
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_EXTERNALLY_CLASSIFIED.value,
                operation_order=2,
                created_at=datetime.now() - timedelta(seconds=1),
            ),
        ]

        self.slice_id0 = uuid.uuid4()
        self.slice_id1 = uuid.uuid4()
        self.emb0 = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )
        self.emb1 = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )
        self.slice_0 = DocumentSlice(
            id=self.slice_id0,
            body="This is a sentence.",
            document_id=doc_id,
            order_sequence=0,
            embedding=self.emb0.tobytes(),
            embedding_model_name="embmodel",
            embedding_model_id=uuid.uuid4(),
        )
        self.slice_1 = DocumentSlice(
            id=self.slice_id1,
            body="This is another sentence.",
            document_id=doc_id,
            order_sequence=1,
            embedding=self.emb1.tobytes(),
            embedding_model_name="embmodel",
            embedding_model_id=uuid.uuid4(),
        )

        self.test_session.add(doc)
        self.test_session.add_all(states)
        self.test_session.add(self.slice_0)
        self.test_session.add(self.slice_1)
        self.test_session.commit()

        classification_harmonizer.main()

        states = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == doc_id)
            .all()
        )

        most_recent_state = max(states, key=lambda x: x.created_at.timestamp())

        self.assertEqual(Step.DOCUMENT_CLASSIFIED_SDG.value, most_recent_state.title)

        for s_id in [self.slice_id0, self.slice_id1]:
            sdgs = (
                self.test_session.query(Sdg)
                .filter(Sdg.slice_id == s_id)
                .all()
            )
            self.assertListEqual([s.sdg_number for s in sdgs], external_sdgs)