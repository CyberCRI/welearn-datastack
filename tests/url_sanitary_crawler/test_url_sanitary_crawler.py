import os
import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from welearn_database.data.enumeration import Step
from welearn_database.data.models import (
    Base,
    Category,
    Corpus,
    ErrorRetrieval,
    ProcessState,
    WeLearnDocument,
)

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.enumerations import URLStatus
from welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler import (
    main,
)


class Test(TestCase):
    def setUp(self) -> None:
        os.environ["PG_DRIVER"] = "sqlite"
        os.environ["PG_USER"] = ""
        os.environ["PG_PASSWORD"] = ""  # nosec
        os.environ["PG_HOST"] = ""
        os.environ["PG_DB"] = ":memory:"
        self.path_test_input = Path(__file__).parent.parent / "resources" / "input"
        self.path_test_input.mkdir(parents=True, exist_ok=True)
        os.environ["ARTIFACT_ROOT"] = self.path_test_input.parent.as_posix()

        self.engine = create_engine("sqlite://")
        s_maker = sessionmaker(self.engine)
        handle_schema_with_sqlite(self.engine)

        self.test_session = s_maker()
        Base.metadata.create_all(self.test_session.get_bind())

        self.category_name = "categroy_test0"
        self.category_id = uuid.uuid4()

        self.category = Category(id=self.category_id, title=self.category_name)

        self.test_session.add(self.category)

        corpus_source_name0 = "corpus0"
        corpus_source_name1 = "corpus1"
        corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name0,
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
        )
        corpus_test1 = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name1,
            is_fix=True,
            category_id=self.category_id,
            is_active=True,
        )

        self.doc_test_id0 = uuid.UUID("87c88599-2baa-400d-8c9b-1ddd61e3b490")
        self.doc_test_id1 = uuid.UUID("6a4ac0a1-b5a2-4df1-9a2e-f6b4abe1c6db")
        self.doc_test_id2 = uuid.UUID("d5f2586c-9395-45dc-911e-5820e0300aa6")
        doc_test0 = WeLearnDocument(
            id=self.doc_test_id0,
            url="https://example.org",
            corpus_id=corpus_test.id,
            title="test",
            lang="en",
            full_content="test test test test test test test test test test test test test test test test test test test ",
            description="test",
            details={"test": "test"},
        )
        doc_test1 = WeLearnDocument(
            id=self.doc_test_id1,
            url="https://example1.org",
            corpus_id=corpus_test.id,
            title="test",
            lang="en",
            full_content="test test test test test test test test test test test test test test test test test test test ",
            description="test",
            details={"test": "test"},
        )
        doc_test2 = WeLearnDocument(
            id=self.doc_test_id2,
            url="https://example2.org",
            corpus_id=corpus_test1.id,
            title="test",
            lang="en",
            full_content="test test test test test test test test test test test test test test test test test test test ",
            description="test",
            details={"test": "test"},
        )

        process_state0 = ProcessState(
            document_id=self.doc_test_id0,
            title=Step.DOCUMENT_IN_QDRANT.value,
            id=uuid.uuid4(),
        )
        process_state1 = ProcessState(
            document_id=self.doc_test_id1,
            title=Step.DOCUMENT_IN_QDRANT.value,
            id=uuid.uuid4(),
        )
        process_state2 = ProcessState(
            document_id=self.doc_test_id2,
            title=Step.DOCUMENT_IN_QDRANT.value,
            id=uuid.uuid4(),
        )
        self.test_session.add(corpus_test)
        self.test_session.add(corpus_test1)
        self.test_session.add(doc_test0)
        self.test_session.add(doc_test1)
        self.test_session.add(doc_test2)
        self.test_session.add(process_state0)
        self.test_session.add(process_state1)
        self.test_session.add(process_state2)

        self.test_session.commit()

    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.check_url"
    )
    def test_main(
        self, mock_check_url, mock_reyrieve_ids_from_csv, mock_create_db_session
    ):

        mock_create_db_session.return_value = self.test_session
        mock_reyrieve_ids_from_csv.return_value = [
            self.doc_test_id0,
            self.doc_test_id1,
            self.doc_test_id2,
        ]

        def _status_by_url(url: str):
            status_map = {
                "https://example.org": (URLStatus.VALID, 200),
                "https://example1.org": (URLStatus.UPDATE, 314),
                "https://example2.org": (URLStatus.DELETE, 404),
            }
            return status_map[url]

        mock_check_url.side_effect = _status_by_url

        main()

        ps_doc0 = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == self.doc_test_id0)
            .all()
        )
        ps_doc1 = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == self.doc_test_id1)
            .all()
        )
        ps_doc2 = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == self.doc_test_id2)
            .all()
        )

        ps_doc0.sort(key=lambda x: x.operation_order)
        ps_doc1.sort(key=lambda x: x.operation_order)
        ps_doc2.sort(key=lambda x: x.operation_order)

        self.assertEqual(len(ps_doc0), 1)
        self.assertEqual(len(ps_doc1), 2)
        self.assertEqual(len(ps_doc2), 2)

        self.assertEqual(ps_doc1[-1].title.lower(), "url_retrieved")
        self.assertEqual(ps_doc2[-1].title.lower(), "document_is_irretrievable")

        err_doc1 = (
            self.test_session.query(ErrorRetrieval)
            .filter(ErrorRetrieval.document_id == self.doc_test_id1)
            .all()
        )
        err_doc2 = (
            self.test_session.query(ErrorRetrieval)
            .filter(ErrorRetrieval.document_id == self.doc_test_id2)
            .all()
        )
        self.assertEqual(len(err_doc1), 1)
        self.assertEqual(err_doc1[0].http_error_code, 314)
        self.assertEqual(len(err_doc2), 1)
        self.assertEqual(err_doc2[0].http_error_code, 404)

    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.check_url"
    )
    def test_main_ignore_unknown_status(
        self, mock_check_url, mock_reyrieve_ids_from_csv, mock_create_db_session
    ):
        mock_create_db_session.return_value = self.test_session
        mock_reyrieve_ids_from_csv.return_value = [self.doc_test_id0]
        mock_check_url.return_value = (URLStatus.UNKNOWN, 599)

        main()

        ps_doc0 = (
            self.test_session.query(ProcessState)
            .filter(ProcessState.document_id == self.doc_test_id0)
            .all()
        )
        err_doc0 = (
            self.test_session.query(ErrorRetrieval)
            .filter(ErrorRetrieval.document_id == self.doc_test_id0)
            .all()
        )

        self.assertEqual(len(ps_doc0), 1)
        self.assertEqual(len(err_doc0), 0)

    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.URLSanitaryCrawler.url_sanitary_crawler.check_url"
    )
    def test_main_no_documents(
        self, mock_check_url, mock_reyrieve_ids_from_csv, mock_create_db_session
    ):
        mock_create_db_session.return_value = self.test_session
        mock_reyrieve_ids_from_csv.return_value = []

        main()

        self.assertEqual(
            self.test_session.query(ProcessState).count(),
            3,
        )
        self.assertEqual(self.test_session.query(ErrorRetrieval).count(), 0)
        mock_check_url.assert_not_called()
