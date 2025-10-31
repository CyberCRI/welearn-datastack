import csv
import os
import random
import shutil
import string
import uuid
from pathlib import Path
from unittest import TestCase, mock
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from welearn_database.data.enumeration import Step
from welearn_database.data.models import (
    Base,
    Category,
    Corpus,
    ProcessState,
    WeLearnDocument,
)

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.nodes_workflow.DocumentHubCollector import document_collector
from welearn_datastack.plugins.interface import IPluginRESTCollector


def random_string(length: int):
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, k=length)  # nosec
    )


corpus_source_name = "test_corpus"


class TestExtractNCollectDocs(TestCase):
    def setUp(self) -> None:
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

        self.path_test_input = Path(__file__).parent.parent / "resources" / "input"
        self.path_test_input.mkdir(parents=True, exist_ok=True)

        os.environ["ARTIFACT_ROOT"] = self.path_test_input.parent.as_posix()
        self.category_name = "categroy_test0"

        self.category_id = uuid.uuid4()
        self.category = Category(id=self.category_id, title=self.category_name)
        self.test_session.add(self.category)

        self.corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
        )
        self.test_session.add(self.corpus_test)
        self.test_session.commit()

        self.doc_valid = WeLearnDocument(
            id=uuid.uuid4(),
            url="https://example.org/wiki/Randomness",
            lang="en",
            full_content=random_string(300),
            description=random_string(100),
            corpus_id=self.corpus_test.id,
        )
        self.doc_invalid = WeLearnDocument(
            id=uuid.uuid4(),
            url="https://example.org/wiki/Unit_testing",
            lang="en",
            full_content=random_string(300),
            description=random_string(100),
            corpus_id=uuid.uuid4(),  # corpus inexistant
        )
        self.test_session.add(self.doc_valid)
        self.test_session.add(self.doc_invalid)
        self.test_session.commit()

    def tearDown(self) -> None:
        self.test_session.close()
        del self.test_session
        shutil.rmtree(self.path_test_input, ignore_errors=True)
        shutil.rmtree(self.path_test_input.parent / "output", ignore_errors=True)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.collector_selector"
    )
    def test_extract_data(self, collector_selector_mock):
        collector_selector_mock.select_collector.return_value = mock.MagicMock(
            spec=IPluginRESTCollector
        )
        collector_selector_mock.select_collector.return_value.run.return_value = [
            WrapperRetrieveDocument(document=self.doc_valid),
            WrapperRetrieveDocument(
                document=self.doc_invalid, error_info="Not found", http_error_code=404
            ),
        ]

        (
            extracted_docs,
            error_docs,
            process_states,
        ) = document_collector.extract_data_from_urls(
            welearn_documents=[self.doc_valid, self.doc_invalid]
        )

        self.assertEqual(len(extracted_docs), 1)
        self.assertEqual(extracted_docs[0].id, self.doc_valid.id)
        self.assertEqual(len(error_docs), 1)
        self.assertEqual(error_docs[0].document_id, self.doc_invalid.id)
        self.assertEqual(len(process_states), 2)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.collector_selector"
    )
    def test_extract_data_corpus_not_found(self, collector_selector_mock):
        # Utilise les documents préparés dans setUp
        collector_selector_mock.select_collector.return_value = mock.MagicMock(
            spec=IPluginRESTCollector
        )
        collector_selector_mock.select_collector.return_value.run.return_value = [
            WrapperRetrieveDocument(document=self.doc_valid)
        ]

        (
            extracted_docs,
            error_docs,
            process_states,
        ) = document_collector.extract_data_from_urls(
            welearn_documents=[self.doc_valid, self.doc_invalid]
        )

        self.assertEqual(len(extracted_docs), 1)
        self.assertEqual(extracted_docs[0].id, self.doc_valid.id)
        self.assertEqual(len(process_states), 1)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.extract_data_from_urls"
    )
    def test_main(self, extract_data_mock, create_db_session_mock):
        create_db_session_mock.return_value = self.test_session
        uuids = [uuid.uuid4() for _ in range(2)]
        wd0 = WeLearnDocument(
            id=uuids[0],
            url="https://example.org/wiki/Randomness__1",
            lang="en",
            full_content=random_string(300),
            description=random_string(100),
            corpus_id=self.corpus_test.id,
        )

        wd1 = WeLearnDocument(
            id=uuids[1],
            url="https://example.org/wiki/Randomness__2",
            lang="en",
            full_content=random_string(300),
            description=random_string(100),
            corpus_id=self.corpus_test.id,
        )

        self.test_session.add(wd0)
        self.test_session.add(wd1)
        self.test_session.commit()

        with (self.path_test_input / "batch_ids.csv").open("w") as f:
            writer = csv.writer(f)
            for uuid_ in uuids:
                writer.writerow([uuid_])

        # Ajout des ProcessState simulés
        process_states = [
            ProcessState(
                id=uuid.uuid4(), document_id=wd0.id, title=Step.DOCUMENT_SCRAPED.value
            ),
            ProcessState(
                id=uuid.uuid4(), document_id=wd1.id, title=Step.DOCUMENT_SCRAPED.value
            ),
        ]
        extract_data_mock.return_value = ([wd0, wd1], [], process_states)

        document_collector.main()

        # Get data from database and check
        for uuid_ in uuids:
            current_doc = (
                self.test_session.query(WeLearnDocument)
                .filter(WeLearnDocument.id == uuid_)
                .one()
            )
            self.assertEqual(current_doc.corpus_id, self.corpus_test.id)
            self.assertEqual(current_doc.corpus.source_name, corpus_source_name)

        # Vérifie la présence des ProcessState
        db_states = list(
            self.test_session.query(ProcessState).filter(
                ProcessState.document_id.in_(uuids)
            )
        )
        self.assertEqual(len(db_states), 2)
        self.assertSetEqual(set([s.document_id for s in db_states]), set(uuids))
        self.assertTrue(all(s.title == Step.DOCUMENT_SCRAPED.value for s in db_states))
