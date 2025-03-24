import unittest
import uuid
from asyncio.subprocess import Process
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from isort.core import process
from numpy.core.defchararray import title
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import Base, Corpus, ProcessState, WeLearnDocument
from welearn_datastack.data.enumerations import Step, URLRetrievalType, WeighedScope
from welearn_datastack.modules.retrieve_data_from_database import (
    retrieve_random_documents_ids_according_process_title,
    retrieve_urls_ids,
)


def octet_length(content):
    return len(content)


class TestRetrieveDataFromDatabase(unittest.TestCase):
    @patch(
        "welearn_datastack.modules.retrieve_data_from_database._generate_query_size_limit"
    )
    def test_should_retrieve_new_urls_ids(self, mock_generate_query):
        session = Mock()
        mock_generate_query.return_value.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [
            ("id1",),
            ("id2",),
        ]
        result = retrieve_urls_ids(session, URLRetrievalType.NEW_MODE)
        self.assertEqual(result, ["id1", "id2"])

    @patch(
        "welearn_datastack.modules.retrieve_data_from_database._generate_query_size_limit"
    )
    def test_should_retrieve_updated_urls_ids(self, mock_generate_query):
        session = Mock()
        mock_generate_query.return_value.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [
            ("id1",),
            ("id2",),
        ]
        result = retrieve_urls_ids(session, URLRetrievalType.UPDATE_MODE)
        self.assertEqual(result, ["id1", "id2"])

    @patch(
        "welearn_datastack.modules.retrieve_data_from_database._generate_query_size_limit"
    )
    def test_should_raise_error_for_invalid_url_retrieval_mode(
        self, mock_generate_query
    ):
        session = Mock()
        with self.assertRaises(ValueError):
            retrieve_urls_ids(session, "invalid_mode")

    def test_retrieve_random_documents_ids_according_process_title(self):
        engine = create_engine("sqlite://")

        @event.listens_for(engine, "connect")
        def connect(conn, rec):
            conn.create_function("octet_length", 1, octet_length)

        s_maker = sessionmaker(engine)
        handle_schema_with_sqlite(engine)

        test_session = s_maker()
        Base.metadata.create_all(test_session.get_bind())

        corpus_source_name0 = "corpus0"
        corpus_source_name1 = "corpus1"
        corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name0,
            is_fix=True,
            is_active=True,
        )
        corpus_test1 = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name1,
            is_fix=True,
            is_active=True,
        )

        doc_test_id0 = uuid.uuid4()
        doc_test_id1 = uuid.uuid4()
        doc_test_id2 = uuid.uuid4()
        doc_test0 = WeLearnDocument(
            id=doc_test_id0,
            url="https://example.org",
            corpus_id=corpus_test.id,
            title="test",
            lang="en",
            full_content="test",
            description="test",
            details={"test": "test"},
            trace=1,
        )
        doc_test1 = WeLearnDocument(
            id=doc_test_id1,
            url="https://example1.org",
            corpus_id=corpus_test.id,
            title="test",
            lang="en",
            full_content="test",
            description="test",
            details={"test": "test"},
            trace=1,
        )
        doc_test2 = WeLearnDocument(
            id=doc_test_id2,
            url="https://example2.org",
            corpus_id=corpus_test1.id,
            title="test",
            lang="en",
            full_content="test",
            description="test",
            details={"test": "test"},
            trace=1,
        )

        process_state0 = ProcessState(
            document_id=doc_test_id0,
            title=Step.DOCUMENT_IN_QDRANT.value,
            id=uuid.uuid4(),
        )
        process_state1 = ProcessState(
            document_id=doc_test_id1,
            title=Step.DOCUMENT_CLASSIFIED_NON_SDG.value,
            id=uuid.uuid4(),
        )
        process_state2 = ProcessState(
            document_id=doc_test_id2,
            title=Step.DOCUMENT_IN_QDRANT.value,
            id=uuid.uuid4(),
        )
        test_session.add(corpus_test)
        test_session.add(corpus_test1)
        test_session.add(doc_test0)
        test_session.add(doc_test1)
        test_session.add(doc_test2)
        test_session.add(process_state0)
        test_session.add(process_state1)
        test_session.add(process_state2)

        test_session.commit()

        res0 = retrieve_random_documents_ids_according_process_title(
            session=test_session, process_titles=[Step.DOCUMENT_IN_QDRANT], qty_max=1
        )

        self.assertEqual(len(res0), 1)
        self.assertIn(res0[0], [str(doc_test_id0), str(doc_test_id2)])

        res1 = retrieve_random_documents_ids_according_process_title(
            session=test_session, process_titles=[Step.DOCUMENT_IN_QDRANT], qty_max=2
        )

        self.assertEqual(len(res1), 2)
        awaited_resp = [str(doc_test_id0), str(doc_test_id2)]
        awaited_resp.sort()
        res1.sort()
        self.assertListEqual(res1, awaited_resp)

        res2 = retrieve_random_documents_ids_according_process_title(
            session=test_session,
            process_titles=[Step.DOCUMENT_IN_QDRANT],
            qty_max=2,
            corpus_name=corpus_test1.source_name,
        )
        res2.sort()
        self.assertEqual(len(res2), 1)
        self.assertListEqual(res2, [str(doc_test_id2)])
