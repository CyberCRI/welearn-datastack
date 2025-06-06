import os
import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import Base, Corpus, ProcessState, WeLearnDocument
from welearn_datastack.data.enumerations import Step, URLStatus
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

        self.doc_test_id0 = uuid.UUID("87c88599-2baa-400d-8c9b-1ddd61e3b490")
        self.doc_test_id1 = uuid.UUID("6a4ac0a1-b5a2-4df1-9a2e-f6b4abe1c6db")
        self.doc_test_id2 = uuid.UUID("d5f2586c-9395-45dc-911e-5820e0300aa6")
        doc_test0 = WeLearnDocument(
            id=self.doc_test_id0,
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
            id=self.doc_test_id1,
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
            id=self.doc_test_id2,
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
        mock_check_url.side_effect = [
            (URLStatus.VALID, 200),
            (URLStatus.UPDATE, 314),
            (URLStatus.DELETE, 404),
        ]

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

        ps_doc1.sort(key=lambda x: x.operation_order)
        ps_doc2.sort(key=lambda x: x.operation_order)

        self.assertEqual(len(ps_doc0), 2)
        self.assertEqual(len(ps_doc1), 1)
        self.assertEqual(len(ps_doc2), 2)

        self.assertEqual(ps_doc0[-1].title.lower(), "url_retrieved")
        self.assertEqual(ps_doc2[-1].title.lower(), "document_is_irretrievable")
