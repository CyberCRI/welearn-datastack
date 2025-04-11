import csv
import os
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy
import sqlalchemy
from qdrant_client import QdrantClient
from qdrant_client.http.models import models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import (
    Base,
    Corpus,
    DocumentSlice,
    ProcessState,
    Sdg,
    WeLearnDocument,
)
from welearn_datastack.data.enumerations import Step
from welearn_datastack.nodes_workflow.QdrantSyncronizer import qdrant_syncronizer
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)


class TestQdrantSyncronizer(unittest.TestCase):
    def setUp(self):
        self.client = QdrantClient(":memory:")

        self.client.create_collection(
            collection_name="collection_en_embmodel",
            vectors_config=models.VectorParams(size=5, distance=models.Distance.COSINE),
        )

        self.client.create_collection(
            collection_name="collection_fr_embmodel",
            vectors_config=models.VectorParams(size=5, distance=models.Distance.COSINE),
        )

        get_sub_environ_according_prefix.cache_clear()
        os.environ["PG_DRIVER"] = "sqlite"
        os.environ["PG_USER"] = ""
        os.environ["PG_PASSWORD"] = ""  # nosec
        os.environ["PG_HOST"] = ""
        os.environ["PG_DB"] = ":memory:"

        self.path_test_input = Path(__file__).parent.parent / "resources" / "input"
        self.path_test_input.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine("sqlite://")
        handle_schema_with_sqlite(self.engine)

        s_maker = sessionmaker(self.engine)
        self.test_session = s_maker()
        Base.metadata.create_all(self.test_session.get_bind())
        os.environ["ARTIFACT_ROOT"] = self.path_test_input.parent.as_posix()

        corpus_source_name = "corpus"

        self.corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
        )

        doc_id = uuid.uuid4()

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
                title=Step.DOCUMENT_KEYWORDS_EXTRACTED.value,
                operation_order=2,
                created_at=datetime.now() - timedelta(seconds=1),
            ),
        ]

        with (self.path_test_input / "batch_ids.csv").open("w") as f:
            writer = csv.writer(f)
            writer.writerow([doc_id])
        self.emb0 = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )
        self.emb1 = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )

        self.slice_id0 = uuid.uuid4()
        self.slice_id1 = uuid.uuid4()

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

        self.sdgs = [
            Sdg(
                id=uuid.uuid4(),
                slice_id=self.slice_id0,
                sdg_number=1,
                bi_classifier_model_id=uuid.uuid4(),
                n_classifier_model_id=uuid.uuid4(),
            ),
            Sdg(
                id=uuid.uuid4(),
                slice_id=self.slice_id1,
                sdg_number=2,
                bi_classifier_model_id=uuid.uuid4(),
                n_classifier_model_id=uuid.uuid4(),
            ),
        ]

        self.docid = doc_id

        self.test_session.add(self.corpus_test)
        self.test_session.add(doc)
        self.test_session.add_all(states)
        self.test_session.add(self.slice_0)
        self.test_session.add(self.slice_1)
        self.test_session.add_all(self.sdgs)

        self.test_session.commit()

    def tearDown(self):
        self.test_session.close()
        os.remove(self.path_test_input / "batch_ids.csv")
        del self.test_session

    @patch(
        "welearn_datastack.nodes_workflow.QdrantSyncronizer.qdrant_syncronizer.QdrantClient"
    )
    @patch(
        "welearn_datastack.nodes_workflow.QdrantSyncronizer.qdrant_syncronizer.create_db_session"
    )
    def test_qdrant_syncronizer(self, mock_create_db_session, mock_qdrant_client):
        os.environ["QDRANT_CHUNK_SIZE"] = "1"
        mock_create_db_session.return_value = self.test_session
        mock_qdrant_client.return_value = self.client

        qdrant_syncronizer.main()

        states = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == self.docid)
            .all()
        )

        most_recent_state = max(states, key=lambda x: x.created_at.timestamp())

        self.assertEqual(Step.DOCUMENT_IN_QDRANT.value, most_recent_state.title)

        ret_values_from_qdrant = self.client.scroll(
            collection_name=f"collection_en_embmodel",
            limit=100,
            with_vectors=True,
        )

        self.assertEqual(2, len(ret_values_from_qdrant[0]))
        for s in ret_values_from_qdrant[0]:
            self.assertIn(uuid.UUID(s.id), [self.slice_id0, self.slice_id1])

            self.assertEqual(s.payload["document_id"], str(self.docid))
            self.assertListEqual(s.payload["document_sdg"], [1, 2])

            if s.id == self.slice_id0:
                self.assertEqual(s.payload["slice_sdg"], 1)
            elif s.id == self.slice_id1:
                self.assertEqual(s.payload["slice_sdg"], 2)
