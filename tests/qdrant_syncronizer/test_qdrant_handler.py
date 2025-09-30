import unittest
import uuid
from datetime import datetime
from unittest.mock import Mock

import numpy
from qdrant_client import QdrantClient
from qdrant_client.http.models import models

from welearn_datastack.modules.qdrant_handler import (  # get_collections_names,
    classify_documents_per_collection,
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
    def __init__(self, document_id, embedding_model_name="embmodel"):
        self.document_id = document_id
        self.embedding_model_name = embedding_model_name
        self.embedding = numpy.random.uniform(low=-1, high=1, size=(50,))
        self.order_sequence = 0
        self.document = FakeDocument(document_id, uuid.uuid4())
        self.id = uuid.uuid4()
        self.embedding_model = Mock(title=embedding_model_name)


class TestQdrantHandler(unittest.TestCase):
    def setUp(self):
        self.client = QdrantClient(":memory:")

        self.client.create_collection(
            collection_name="collection_welearn_en_english-embmodel",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

        self.client.create_collection(
            collection_name="collection_welearn_fr_french-embmodel",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

    def tearDown(self):
        self.client.close()

    def test_should_get_collections_names_for_given_slices(self):
        doc_id = uuid.uuid4()
        qdrant_connector = self.client
        fake_slice = FakeSlice(doc_id, embedding_model_name="english-embmodel")
        fake_slice.id = uuid.uuid4()
        slices = [fake_slice]
        collections_names = classify_documents_per_collection(qdrant_connector, slices)

        expected = {"collection_welearn_en_english-embmodel": {fake_slice.document_id}}
        self.assertEqual(dict(collections_names), expected)

    def test_should_handle_multiple_slices_for_same_collection(self):
        doc_id0 = uuid.uuid4()
        doc_id1 = uuid.uuid4()
        qdrant_connector = self.client
        fake_slice0 = FakeSlice(doc_id0, embedding_model_name="english-embmodel")
        fake_slice1 = FakeSlice(doc_id0, embedding_model_name="english-embmodel")

        fake_slice1.order_sequence = 1

        fake_slice2 = FakeSlice(doc_id1, embedding_model_name="french-embmodel")
        fake_slice2.document.lang = "fr"

        slices = [fake_slice0, fake_slice1, fake_slice2]
        collections_names = classify_documents_per_collection(qdrant_connector, slices)
        expected = {
            "collection_welearn_en_english-embmodel": {doc_id0},
            "collection_welearn_fr_french-embmodel": {doc_id1},
        }
        self.assertEqual(dict(collections_names), expected)

    def test_should_handle_multiple_slices_for_same_collection_with_multi_lingual_collection(
        self,
    ):
        self.client.create_collection(
            collection_name="collection_welearn_mul_mulembmodel",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

        doc_id0 = uuid.uuid4()
        doc_id1 = uuid.uuid4()
        qdrant_connector = self.client
        fake_slice0 = FakeSlice(doc_id0, embedding_model_name="english-embmodel")
        fake_slice1 = FakeSlice(doc_id0, embedding_model_name="english-embmodel")

        fake_slice1.order_sequence = 1

        fake_slice2 = FakeSlice(doc_id1, embedding_model_name="mulembmodel")
        fake_slice2.document.lang = "pt"

        slices = [fake_slice0, fake_slice1, fake_slice2]
        collections_names = classify_documents_per_collection(qdrant_connector, slices)
        expected = {
            "collection_welearn_en_english-embmodel": {doc_id0},
            "collection_welearn_mul_mulembmodel": {doc_id1},
        }
        self.assertDictEqual(dict(collections_names), expected)

    def test_should_handle_multiple_slices_for_same_collection_with_multi_lingual_collection_and_gibberish(
        self,
    ):
        self.client.create_collection(
            collection_name="collection_welearn_mul_mulembmodel_og",
            vectors_config=models.VectorParams(
                size=50, distance=models.Distance.COSINE
            ),
        )

        doc_id0 = uuid.uuid4()
        doc_id1 = uuid.uuid4()
        qdrant_connector = self.client
        fake_slice0 = FakeSlice(doc_id0, embedding_model_name="english-embmodel")
        fake_slice1 = FakeSlice(doc_id0, embedding_model_name="english-embmodel")

        fake_slice1.order_sequence = 1

        fake_slice2 = FakeSlice(doc_id1, embedding_model_name="mulembmodel")
        fake_slice2.document.lang = "pt"

        slices = [fake_slice0, fake_slice1, fake_slice2]
        collections_names = classify_documents_per_collection(qdrant_connector, slices)
        self.assertNotIn("collection_welearn_mul_mulembmodel_og", collections_names)
