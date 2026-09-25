import os
import unittest
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from welearn_database.data.enumeration import Step
from welearn_database.data.models import (
    Base,
    BiClassifierModel,
    Category,
    Corpus,
    CorpusBiClassifierModel,
    CorpusEmbeddingModel,
    CorpusNClassifierModel,
    EmbeddingModel,
    NClassifierModel,
    ProcessState,
    TrackDocumentLatestState,
    WeLearnDocument,
)

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.enumerations import (
    MLModelsType,
    URLRetrievalType,
    WeighedScope,
)
from welearn_datastack.modules.retrieve_data_from_database import (
    retrieve_models,
    retrieve_random_documents_ids_according_process_title,
    retrieve_urls_ids,
)
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)


def octet_length(content):
    return len(content)


class TestRetrieveDataFromDatabase(unittest.TestCase):
    @patch(
        "welearn_datastack.modules.retrieve_data_from_database._generate_query_size_limit"
    )
    def test_should_retrieve_new_urls_ids(self, mock_generate_query):
        session = Mock()
        query = mock_generate_query.return_value
        query.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [
            ("id1",),
            ("id2",),
        ]

        result = retrieve_urls_ids(session, URLRetrievalType.NEW_MODE)

        self.assertEqual(result, ["id1", "id2"])
        mock_generate_query.assert_called_once_with(
            session=session,
            generated_query_goal=WeighedScope.DOCUMENT,
            corpus_name="*",
        )
        self.assertEqual(
            str(query.order_by.call_args.args[0]),
            str(ProcessState.operation_order.desc()),
        )
        self.assertEqual(
            str(query.order_by.return_value.filter.call_args.args[0]),
            str(ProcessState.title == "url_retrieved"),
        )
        query.order_by.return_value.filter.return_value.limit.assert_called_once_with(
            None
        )
        session.close.assert_called_once_with()

    @patch(
        "welearn_datastack.modules.retrieve_data_from_database._generate_query_size_limit"
    )
    def test_should_retrieve_updated_urls_ids(self, mock_generate_query):
        session = Mock()
        query = mock_generate_query.return_value
        query.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [
            ("id1",),
            ("id2",),
        ]

        fixed_now = datetime(2024, 1, 10, 12, 0, 0)
        with patch(
            "welearn_datastack.modules.retrieve_data_from_database.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = fixed_now

            result = retrieve_urls_ids(session, URLRetrievalType.UPDATE_MODE)

        self.assertEqual(result, ["id1", "id2"])
        self.assertEqual(
            str(query.order_by.return_value.filter.call_args.args[0]),
            str(
                (ProcessState.title == "document_in_qdrant")
                & (ProcessState.created_at < (fixed_now - timedelta(hours=2)))
            ),
        )
        query.order_by.return_value.filter.return_value.limit.assert_called_once_with(
            None
        )
        session.close.assert_called_once_with()

    @patch(
        "welearn_datastack.modules.retrieve_data_from_database._generate_query_size_limit"
    )
    def test_should_raise_error_for_invalid_url_retrieval_mode(
        self, mock_generate_query
    ):
        session = Mock()
        with self.assertRaises(ValueError):
            retrieve_urls_ids(
                session, cast(URLRetrievalType, cast(object, "invalid_mode"))
            )

    def test_retrieve_random_documents_ids_according_process_title(self):
        session = Mock()
        query = Mock()
        first_id = uuid.uuid4()
        second_id = uuid.uuid4()
        session.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [
            SimpleNamespace(document_id=first_id),
            SimpleNamespace(document_id=second_id),
        ]

        result = retrieve_random_documents_ids_according_process_title(
            session=session,
            process_titles=[Step.DOCUMENT_IN_QDRANT],
            qty_max=2,
        )

        session.query.assert_called_once_with(TrackDocumentLatestState)
        self.assertEqual(
            str(query.filter.call_args_list[0].args[0]),
            str(TrackDocumentLatestState.title.in_([Step.DOCUMENT_IN_QDRANT.value])),
        )
        self.assertEqual(str(query.order_by.call_args.args[0]), str(func.random()))
        query.limit.assert_called_once_with(2)
        self.assertEqual(result, [str(first_id), str(second_id)])

    def test_retrieve_random_documents_ids_according_process_title_with_threshold(self):
        session = Mock()
        query = Mock()
        document_id = uuid.uuid4()
        session.query.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [SimpleNamespace(document_id=document_id)]

        fixed_now = datetime(2024, 1, 10, 12, 0, 0)
        with patch(
            "welearn_datastack.modules.retrieve_data_from_database.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = fixed_now

            result = retrieve_random_documents_ids_according_process_title(
                session=session,
                process_titles=[Step.DOCUMENT_IN_QDRANT],
                qty_max=1,
                threshold_time_window_in_days=7,
            )

        self.assertEqual(result, [str(document_id)])
        self.assertEqual(query.filter.call_count, 2)
        self.assertEqual(
            str(query.filter.call_args_list[1].args[0]),
            str(TrackDocumentLatestState.created_at < (fixed_now - timedelta(days=7))),
        )
        query.limit.assert_called_once_with(1)

    def test_retrieve_bi_models(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        engine = create_engine("sqlite://")
        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        self.category_name = "category_test0"

        self.category_id = uuid.uuid4()

        self.category = Category(id=self.category_id, title=self.category_name)

        test_session.add(self.category)

        corpus_source_name = "test_corpus"

        corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
        )
        test_session.add(corpus_test)
        test_session.commit()

        bi_classifier_en_id = uuid.uuid4()
        biclassifier_en_test = BiClassifierModel(
            title="test_classifier",
            id=bi_classifier_en_id,
            lang="en",
            used_since=datetime.now() - timedelta(days=1),
        )

        corpus_bi_classifier_en_test = CorpusBiClassifierModel(
            corpus_id=corpus_test.id,
            bi_classifier_model_id=bi_classifier_en_id,
            used_since=datetime.now() - timedelta(days=1),
        )

        bi_classifier_en_id2 = uuid.uuid4()
        biclassifier_en_test2 = BiClassifierModel(
            title="test_classifier2",
            id=bi_classifier_en_id2,
            lang="en",
            used_since=datetime.now() - timedelta(days=10),
        )
        corpus_bi_classifier_en_test2 = CorpusBiClassifierModel(
            corpus_id=corpus_test.id,
            bi_classifier_model_id=bi_classifier_en_id2,
            used_since=datetime.now() - timedelta(days=10),
        )

        bi_classifier_fr_id = uuid.uuid4()
        biclassifier_fr_test = BiClassifierModel(
            title="test_classifier_fr",
            id=bi_classifier_fr_id,
            lang="fr",
            used_since=datetime.now() - timedelta(days=1),
        )

        corpus_bi_classifier_fr_test = CorpusBiClassifierModel(
            corpus_id=corpus_test.id,
            bi_classifier_model_id=bi_classifier_fr_id,
            used_since=datetime.now() - timedelta(days=1),
        )

        doc_test_id = uuid.uuid4()
        doc_test = WeLearnDocument(
            id=doc_test_id,
            url="https://example.org",
            corpus_id=corpus_test.id,
            title="test title",
            lang="en",
            full_content="test content test content test content test content test content test content test content test content test content test content test content ",
            description="test description vdescription",
            details={"test key details": "test details"},
        )

        test_session.add(biclassifier_en_test2)
        test_session.add(corpus_bi_classifier_en_test2)
        test_session.add(biclassifier_en_test)
        test_session.add(corpus_bi_classifier_en_test)
        test_session.add(biclassifier_fr_test)
        test_session.add(corpus_bi_classifier_fr_test)
        test_session.add(doc_test)
        test_session.commit()

        res = retrieve_models(
            documents_ids=[doc_test_id],
            db_session=test_session,
            ml_type=MLModelsType.BI_CLASSIFIER,
        )

        self.assertEqual(
            res,
            {
                doc_test_id: {
                    "model_id": bi_classifier_en_id,
                    "model_name": biclassifier_en_test.title,
                }
            },
        )

    def test_retrieve_bi_models_no_models(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        engine = create_engine("sqlite://")
        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        doc_test_id = uuid.uuid4()

        res = retrieve_models(
            documents_ids=[doc_test_id],
            db_session=test_session,
            ml_type=MLModelsType.BI_CLASSIFIER,
        )

        self.assertEqual(res, {})

    def test_retrieve_n_models(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        engine = create_engine("sqlite://")
        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        corpus_source_name = "test_corpus"
        category_id = uuid.uuid4()
        category_name = "test"
        category = Category(id=category_id, title=category_name)

        test_session.add(category)

        corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=category_id,
        )
        test_session.add(corpus_test)
        test_session.commit()

        n_classifier_en_id = uuid.uuid4()
        nclassifier_en_test = NClassifierModel(
            title="test_n_classifier",
            id=n_classifier_en_id,
            lang="en",
            used_since=datetime.now() - timedelta(days=1),
        )

        corpus_n_classifier_en_test = CorpusNClassifierModel(
            corpus_id=corpus_test.id,
            n_classifier_model_id=n_classifier_en_id,
            used_since=datetime.now() - timedelta(days=1),
        )

        n_classifier_en_id2 = uuid.uuid4()
        nclassifier_en_test2 = NClassifierModel(
            title="test_n_classifier2",
            id=n_classifier_en_id2,
            lang="en",
            used_since=datetime.now() - timedelta(days=10),
        )
        corpus_n_classifier_en_test2 = CorpusNClassifierModel(
            corpus_id=corpus_test.id,
            n_classifier_model_id=n_classifier_en_id2,
            used_since=datetime.now() - timedelta(days=10),
        )

        n_classifier_fr_id = uuid.uuid4()
        nclassifier_fr_test = NClassifierModel(
            title="test_n_classifier_fr",
            id=n_classifier_fr_id,
            lang="fr",
            used_since=datetime.now() - timedelta(days=1),
        )

        corpus_n_classifier_fr_test = CorpusNClassifierModel(
            corpus_id=corpus_test.id,
            n_classifier_model_id=n_classifier_fr_id,
            used_since=datetime.now() - timedelta(days=1),
        )

        doc_test_id = uuid.uuid4()
        doc_test = WeLearnDocument(
            id=doc_test_id,
            url="https://example.org",
            corpus_id=corpus_test.id,
            title="test title",
            lang="en",
            full_content="test test content test content test content test content test content test content test content",
            description="test description",
            details={"test key details": "test details"},
        )
        test_session.add(nclassifier_en_test2)
        test_session.add(corpus_n_classifier_en_test2)
        test_session.add(nclassifier_en_test)
        test_session.add(corpus_n_classifier_en_test)
        test_session.add(nclassifier_fr_test)
        test_session.add(corpus_n_classifier_fr_test)
        test_session.add(doc_test)
        test_session.commit()

        res = retrieve_models(
            documents_ids=[doc_test_id],
            db_session=test_session,
            ml_type=MLModelsType.N_CLASSIFIER,
        )

        self.assertEqual(
            res,
            {
                doc_test_id: {
                    "model_id": n_classifier_en_id,
                    "model_name": nclassifier_en_test.title,
                }
            },
        )

    def test_retrieve_n_models_no_models(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        engine = create_engine("sqlite://")
        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        doc_test_id = uuid.uuid4()

        res = retrieve_models(
            documents_ids=[doc_test_id],
            db_session=test_session,
            ml_type=MLModelsType.N_CLASSIFIER,
        )

        self.assertEqual(res, {})

    def test_retrieve_embedding_models(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        engine = create_engine("sqlite://")
        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        category_id = uuid.uuid4()
        category_name = "test"
        category = Category(id=category_id, title=category_name)

        test_session.add(category)

        corpus_source_name = "test_corpus"

        corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=category_id,
        )
        test_session.add(corpus_test)
        test_session.commit()

        embedding_model_en_id = uuid.uuid4()
        embedding_model_en_test = EmbeddingModel(
            title="test_embedding_model",
            id=embedding_model_en_id,
            lang="en",
        )

        corpus_embedding_model_en_test = CorpusEmbeddingModel(
            corpus_id=corpus_test.id,
            embedding_model_id=embedding_model_en_id,
            used_since=datetime.now() - timedelta(days=1),
        )

        embedding_model_en_id2 = uuid.uuid4()
        embedding_model_en_test2 = EmbeddingModel(
            title="test_embedding_model2",
            id=embedding_model_en_id2,
            lang="en",
        )
        corpus_embedding_model_en_test2 = CorpusEmbeddingModel(
            corpus_id=corpus_test.id,
            embedding_model_id=embedding_model_en_id2,
            used_since=datetime.now() - timedelta(days=10),
        )

        embedding_model_fr_id = uuid.uuid4()
        embedding_model_fr_test = EmbeddingModel(
            title="test_embedding_model_fr",
            id=embedding_model_fr_id,
            lang="fr",
        )

        corpus_embedding_model_fr_test = CorpusEmbeddingModel(
            corpus_id=corpus_test.id,
            embedding_model_id=embedding_model_fr_id,
            used_since=datetime.now() - timedelta(days=1),
        )

        doc_test_id = uuid.uuid4()
        doc_test = WeLearnDocument(
            id=doc_test_id,
            url="https://example.org",
            corpus_id=corpus_test.id,
            title="test title",
            lang="en",
            full_content="test content test content test content vtest content test content test content ",
            description="test description",
            details={"test key details": "test details"},
        )

        test_session.add(embedding_model_en_test2)
        test_session.add(corpus_embedding_model_en_test2)
        test_session.add(embedding_model_en_test)
        test_session.add(corpus_embedding_model_en_test)
        test_session.add(embedding_model_fr_test)
        test_session.add(corpus_embedding_model_fr_test)
        test_session.add(doc_test)
        test_session.commit()

        res = retrieve_models(
            documents_ids=[doc_test_id],
            db_session=test_session,
            ml_type=MLModelsType.EMBEDDING,
        )

        self.assertEqual(
            res,
            {
                doc_test_id: {
                    "model_id": embedding_model_en_id,
                    "model_name": embedding_model_en_test.title,
                }
            },
        )

    def test_retrieve_embedding_models_no_models(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        engine = create_engine("sqlite://")
        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        doc_test_id = uuid.uuid4()

        res = retrieve_models(
            documents_ids=[doc_test_id],
            db_session=test_session,
            ml_type=MLModelsType.EMBEDDING,
        )

        self.assertEqual(res, {})
