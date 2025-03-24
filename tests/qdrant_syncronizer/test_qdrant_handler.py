import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy
from qdrant_client import QdrantClient
from qdrant_client.http.models import models

from welearn_datastack.data.db_models import DocumentSlice
from welearn_datastack.exceptions import NoPreviousCollectionError, VersionNumberError
from welearn_datastack.modules.qdrant_handler import (  # get_collections_names,
    classify_documents_per_collection,
    extract_version_number,
    get_last_collection_version,
)


class Collection:
    def __init__(self, name):
        self.name = name


class FakeCorpus:
    def __init__(self, corpus_id):
        self.id = corpus_id
        self.source_name = "corpus"
        self.is_fix = True


class FakeDocument:
    def __init__(self, document_id, corpus_id):
        self.id = document_id
        self.title = "title"
        self.description = (
            "This is a description of the document that is used for testing"
        )
        self.lang = "en"
        self.details = {}
        self.trace = 123456789
        self.full_content = (
            "This is the full content of the document that is used for testing"
        )
        self.corpus = FakeCorpus(corpus_id)
        self.corpus_id = corpus_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


class FakeSlice:
    def __init__(self, document_id):
        self.document_id = document_id
        self.embedding_model_name = "embmodel"
        self.embedding = numpy.random.uniform(low=-1, high=1, size=(50,))
        self.order_sequence = 0
        self.document = FakeDocument(document_id, uuid.uuid4())


class TestQdrantHandler(unittest.TestCase):
    def setUp(self):
        get_last_collection_version.cache_clear()

        self.client = QdrantClient(":memory:")

        self.client.create_collection(
            collection_name="collection_corpus_en_embmodel_v0",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

        self.client.create_collection(
            collection_name="collection_corpus_en_embmodel_v1",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

        self.client.create_collection(
            collection_name="collection_corpus_fr_embmodel_v1",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

        self.client.create_collection(
            collection_name="collection_corpus_en_embmodel_v2",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

    def tearDown(self):
        self.client.close()

    def test_should_extract_valid_version_number(self):
        collection_name = "collection_corpus_en_embmodel_v0"
        version_number = extract_version_number(collection_name)
        self.assertEqual(version_number, 0)

    def test_should_raise_error_for_invalid_version_number(self):
        collection_name = "collection_corpus_en_embmodel_vX"
        with self.assertRaises(VersionNumberError):
            extract_version_number(collection_name)

    def test_should_return_last_collection_version(self):
        qdrant_connector = self.client
        version_number = get_last_collection_version(
            "collection_corpus_en_embmodel", qdrant_connector
        )
        self.assertEqual(version_number, 2)

    def test_should_raise_error_when_no_previous_collection_found(self):
        qdrant_connector = self.client
        with self.assertRaises(NoPreviousCollectionError):
            get_last_collection_version(
                "collection_corpus_en_embmodel2", qdrant_connector
            )

    def test_should_get_collections_names_for_given_slices(self):
        doc_id = uuid.uuid4()
        qdrant_connector = self.client
        fake_slice = FakeSlice(doc_id)
        slices = [fake_slice]
        collections_names = classify_documents_per_collection(qdrant_connector, slices)
        expected = {"collection_corpus_en_embmodel_v2": {fake_slice.document_id}}
        self.assertEqual(collections_names, expected)

    def test_should_handle_multiple_slices_for_same_collection(self):
        doc_id0 = uuid.uuid4()
        doc_id1 = uuid.uuid4()
        qdrant_connector = self.client
        fake_slice0 = FakeSlice(doc_id0)
        fake_slice1 = FakeSlice(doc_id0)

        fake_slice1.order_sequence = 1

        fake_slice2 = FakeSlice(doc_id1)
        fake_slice2.document.lang = "fr"

        slices = [fake_slice0, fake_slice1, fake_slice2]
        collections_names = classify_documents_per_collection(qdrant_connector, slices)
        expected = {
            "collection_corpus_en_embmodel_v2": {doc_id0},
            "collection_corpus_fr_embmodel_v1": {doc_id1},
        }
        self.assertEqual(collections_names, expected)
