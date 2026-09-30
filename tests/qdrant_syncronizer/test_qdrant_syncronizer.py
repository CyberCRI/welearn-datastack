import csv
import os
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy
from qdrant_client import QdrantClient
from qdrant_client.http.models import UpdateResult, UpdateStatus, models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from welearn_database.data.enumeration import Step
from welearn_database.data.models import (
    Base,
    Category,
    Corpus,
    DocumentSlice,
    EmbeddingModel,
    ProcessState,
    Sdg,
    WeLearnDocument,
)

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.modules.retrieve_data_from_database import main_corpus_dict
from welearn_datastack.nodes_workflow.QdrantSyncronizer import qdrant_syncronizer
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)


class TestQdrantSyncronizer(unittest.TestCase):
    def setUp(self):
        self.client = QdrantClient(":memory:")

        self.client.create_collection(
            collection_name="collection_welearn_en_english-embmodel",
            vectors_config=models.VectorParams(size=5, distance=models.Distance.COSINE),
        )

        self.client.create_collection(
            collection_name="collection_welearn_fr_french-embmodel",
            vectors_config=models.VectorParams(size=5, distance=models.Distance.COSINE),
        )
        main_corpus_dict.clear()

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

        self.category_name = "category_test0"

        self.category_id = uuid.uuid4()

        self.category = Category(id=self.category_id, title=self.category_name)

        self.test_session.add(self.category)

        self.emb_model_id = uuid.uuid4()
        self.emb_model = EmbeddingModel(
            id=self.emb_model_id, title="english-embmodel", lang="en"
        )
        self.test_session.add(self.emb_model)
        corpus_source_name = "corpus"

        self.corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
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
            embedding_model_name=self.emb_model.title,
            embedding_model_id=self.emb_model_id,
        )
        self.slice_1 = DocumentSlice(
            id=self.slice_id1,
            body="This is another sentence.",
            document_id=doc_id,
            order_sequence=1,
            embedding=self.emb1.tobytes(),
            embedding_model_name=self.emb_model.title,
            embedding_model_id=self.emb_model_id,
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
        self.client.close()
        main_corpus_dict.clear()
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
            collection_name=f"collection_welearn_en_english-embmodel",
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


class TestQdrantSyncronizerFunctions(unittest.TestCase):
    def setUp(self):
        main_corpus_dict.clear()
        self.client = QdrantClient(":memory:")
        self.client.create_collection(
            collection_name="collection_welearn_en_english-embmodel",
            vectors_config=models.VectorParams(size=5, distance=models.Distance.COSINE),
        )

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

        self.category = Category(id=uuid.uuid4(), title="category")
        self.embedding_model = EmbeddingModel(
            id=uuid.uuid4(), title="english-embmodel", lang="en"
        )
        self.test_session.add(self.category)
        self.test_session.add(self.embedding_model)
        self.test_session.commit()

    def tearDown(self):
        self.test_session.close()
        self.client.close()
        main_corpus_dict.clear()

    def _create_corpus(self, source_name: str, parent_corpus: Corpus | None = None):
        corpus = Corpus(
            id=uuid.uuid4(),
            source_name=source_name,
            is_fix=True,
            is_active=True,
            category_id=self.category.id,
            parent_corpus_id=(parent_corpus.id if parent_corpus is not None else None),
        )
        self.test_session.add(corpus)
        return corpus

    def _create_document(self, corpus: Corpus, steps: list[Step], title: str = "test"):
        doc = WeLearnDocument(
            id=uuid.uuid4(),
            title=title,
            url=f"https://example.org/{title}",
            lang="en",
            full_content="Sentence A. Sentence B. Sentence C.",
            corpus=corpus,
            description=f"description {title}",
            details={"title": title},
        )
        self.test_session.add(doc)

        base_time = datetime.now() - timedelta(seconds=len(steps) + 1)
        for order, step in enumerate(steps):
            self.test_session.add(
                ProcessState(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    title=step.value,
                    operation_order=order,
                    created_at=base_time + timedelta(seconds=order),
                )
            )

        return doc

    def _create_slice(
        self,
        document: WeLearnDocument,
        order_sequence: int,
        body: str,
    ):
        embedding = numpy.random.uniform(low=-1, high=1, size=(5,)).astype(
            numpy.float32
        )
        doc_slice = DocumentSlice(
            id=uuid.uuid4(),
            body=body,
            document_id=document.id,
            order_sequence=order_sequence,
            embedding=embedding.tobytes(),
            embedding_model_name=self.embedding_model.title,
            embedding_model_id=self.embedding_model.id,
        )
        self.test_session.add(doc_slice)
        return doc_slice, embedding

    def _create_sdg(self, doc_slice: DocumentSlice, sdg_number: int):
        sdg = Sdg(
            id=uuid.uuid4(),
            slice_id=doc_slice.id,
            sdg_number=sdg_number,
            bi_classifier_model_id=uuid.uuid4(),
            n_classifier_model_id=uuid.uuid4(),
        )
        self.test_session.add(sdg)
        return sdg

    def _fetch_states(self, document_id: uuid.UUID):
        return (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == document_id)
            .all()
        )

    def test_group_slice_by_document_id_groups_slices_per_document(self):
        root_corpus = self._create_corpus("root")
        doc0 = self._create_document(root_corpus, [Step.DOCUMENT_SCRAPED], "doc0")
        doc1 = self._create_document(root_corpus, [Step.DOCUMENT_SCRAPED], "doc1")
        slice_0, _ = self._create_slice(doc0, 0, "doc0-a")
        slice_1, _ = self._create_slice(doc0, 1, "doc0-b")
        slice_2, _ = self._create_slice(doc1, 0, "doc1-a")

        grouped = qdrant_syncronizer.group_slice_by_document_id(
            [slice_0, slice_1, slice_2]
        )

        self.assertCountEqual(grouped.keys(), [doc0.id, doc1.id])
        self.assertListEqual(grouped[doc0.id], [slice_0, slice_1])
        self.assertListEqual(grouped[doc1.id], [slice_2])

    def test_flag_documents_with_no_collection_marks_trace_and_removes_none_bucket(
        self,
    ):
        root_corpus = self._create_corpus("root")
        doc0 = self._create_document(root_corpus, [Step.DOCUMENT_SCRAPED], "doc0")
        doc1 = self._create_document(root_corpus, [Step.DOCUMENT_SCRAPED], "doc1")
        self.test_session.commit()

        documents_per_collection = {
            None: {doc0.id, doc1.id},
            "collection_welearn_en_english-embmodel": set(),
        }

        qdrant_syncronizer.flag_documents_with_no_collection(
            self.test_session, documents_per_collection
        )

        self.assertNotIn(None, documents_per_collection)
        for document_id in [doc0.id, doc1.id]:
            titles = [state.title for state in self._fetch_states(document_id)]
            self.assertIn(Step.KEPT_FOR_TRACE.value, titles)

    def test_generate_needed_qdrant_points_supports_root_and_sub_corpus_and_skips_slices_without_sdg(
        self,
    ):
        root_corpus = self._create_corpus("root")
        child_corpus = self._create_corpus("child", parent_corpus=root_corpus)

        root_doc = self._create_document(
            root_corpus,
            [Step.DOCUMENT_SCRAPED, Step.DOCUMENT_KEYWORDS_EXTRACTED],
            "root",
        )
        child_doc = self._create_document(
            child_corpus,
            [Step.DOCUMENT_SCRAPED, Step.DOCUMENT_KEYWORDS_EXTRACTED],
            "child",
        )

        root_slice_0, root_emb_0 = self._create_slice(root_doc, 0, "root-a")
        root_slice_1, _ = self._create_slice(root_doc, 1, "root-b")
        self._create_slice(root_doc, 2, "root-c-without-sdg")

        child_slice_0, _ = self._create_slice(child_doc, 0, "child-a")
        child_slice_1, _ = self._create_slice(child_doc, 1, "child-b")
        child_slice_2, _ = self._create_slice(child_doc, 2, "child-c")

        self._create_sdg(root_slice_0, 1)
        self._create_sdg(root_slice_1, 1)
        self._create_sdg(child_slice_0, 2)
        self._create_sdg(child_slice_1, 2)
        self._create_sdg(child_slice_2, 3)
        self.test_session.commit()

        slices = (
            self.test_session.query(DocumentSlice)
            .filter(DocumentSlice.document_id.in_([root_doc.id, child_doc.id]))
            .order_by(DocumentSlice.document_id, DocumentSlice.order_sequence)
            .all()
        )

        points = qdrant_syncronizer.generate_needed_qdrant_points(
            self.test_session,
            [root_doc.id, child_doc.id],
            qdrant_syncronizer.group_slice_by_document_id(slices),
        )

        self.assertEqual(5, len(points))
        payloads_by_slice_id = {uuid.UUID(point.id): point.payload for point in points}

        self.assertNotIn(
            next(
                doc_slice.id
                for doc_slice in slices
                if doc_slice.body == "root-c-without-sdg"
            ),
            payloads_by_slice_id,
        )

        root_payload = payloads_by_slice_id[root_slice_0.id]
        self.assertEqual("root", root_payload["document_corpus"])
        self.assertIsNone(root_payload["document_sub_corpus"])
        self.assertListEqual([1], root_payload["document_sdg"])
        self.assertListEqual(root_emb_0.tolist(), points[0].vector)

        child_payload = payloads_by_slice_id[child_slice_0.id]
        self.assertEqual("root", child_payload["document_corpus"])
        self.assertEqual("child", child_payload["document_sub_corpus"])
        self.assertListEqual([2, 3], child_payload["document_sdg"])

    def test_adding_new_process_state_only_persists_for_success_status(self):
        root_corpus = self._create_corpus("root")
        document = self._create_document(root_corpus, [Step.DOCUMENT_SCRAPED], "doc")
        self.test_session.commit()

        qdrant_syncronizer.adding_new_process_state(
            "collection_welearn_en_english-embmodel",
            self.test_session,
            [document.id],
            UpdateResult(operation_id=1, status=UpdateStatus.WAIT_TIMEOUT),
        )

        self.assertNotIn(
            Step.DOCUMENT_IN_QDRANT.value,
            [state.title for state in self._fetch_states(document.id)],
        )

        qdrant_syncronizer.adding_new_process_state(
            "collection_welearn_en_english-embmodel",
            self.test_session,
            [document.id],
            UpdateResult(operation_id=2, status=UpdateStatus.COMPLETED),
        )

        self.assertIn(
            Step.DOCUMENT_IN_QDRANT.value,
            [state.title for state in self._fetch_states(document.id)],
        )

    def test_handle_collection_replaces_existing_points_and_flags_non_ready_documents(
        self,
    ):
        root_corpus = self._create_corpus("root")

        ready_document = self._create_document(
            root_corpus,
            [
                Step.DOCUMENT_SCRAPED,
                Step.DOCUMENT_VECTORIZED,
                Step.DOCUMENT_KEYWORDS_EXTRACTED,
            ],
            "ready",
        )
        trace_document = self._create_document(
            root_corpus,
            [Step.DOCUMENT_SCRAPED, Step.DOCUMENT_VECTORIZED],
            "trace",
        )

        ready_slice_0, _ = self._create_slice(ready_document, 0, "ready-a")
        ready_slice_1, _ = self._create_slice(ready_document, 1, "ready-b")
        trace_slice_0, _ = self._create_slice(trace_document, 0, "trace-a")

        self._create_sdg(ready_slice_0, 1)
        self._create_sdg(ready_slice_1, 2)
        self._create_sdg(trace_slice_0, 4)
        self.test_session.commit()

        stale_ready_point_id = str(uuid.uuid4())
        stale_trace_point_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name="collection_welearn_en_english-embmodel",
            points=[
                models.PointStruct(
                    id=stale_ready_point_id,
                    vector=[0.0] * 5,
                    payload={"document_id": str(ready_document.id)},
                ),
                models.PointStruct(
                    id=stale_trace_point_id,
                    vector=[0.0] * 5,
                    payload={"document_id": str(trace_document.id)},
                ),
            ],
            wait=True,
        )

        slices = (
            self.test_session.query(DocumentSlice)
            .filter(
                DocumentSlice.document_id.in_([ready_document.id, trace_document.id])
            )
            .order_by(DocumentSlice.document_id, DocumentSlice.order_sequence)
            .all()
        )

        qdrant_syncronizer.handle_collection(
            self.test_session,
            {
                "collection_welearn_en_english-embmodel": {
                    ready_document.id,
                    trace_document.id,
                }
            },
            self.client,
            True,
            qdrant_syncronizer.group_slice_by_document_id(slices),
        )

        qdrant_points, _ = self.client.scroll(
            collection_name="collection_welearn_en_english-embmodel",
            limit=100,
            with_payload=True,
        )

        self.assertEqual(2, len(qdrant_points))
        self.assertSetEqual(
            {point.payload["document_id"] for point in qdrant_points},
            {str(ready_document.id)},
        )
        self.assertNotIn(stale_ready_point_id, {point.id for point in qdrant_points})
        self.assertNotIn(stale_trace_point_id, {point.id for point in qdrant_points})

        ready_titles = [state.title for state in self._fetch_states(ready_document.id)]
        trace_titles = [state.title for state in self._fetch_states(trace_document.id)]
        self.assertIn(Step.DOCUMENT_IN_QDRANT.value, ready_titles)
        self.assertIn(Step.KEPT_FOR_TRACE.value, trace_titles)
