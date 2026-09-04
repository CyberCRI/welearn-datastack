import csv
import os
import random
import shutil
import string
import uuid
from pathlib import Path
from typing import cast
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
from welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector import (
    filter_on_trace,
)
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

        # Setup for filter_on_trace tests
        self.category_filter_id = uuid.uuid4()
        self.category_filter = Category(
            id=self.category_filter_id, title="test_category"
        )
        self.test_session.add(self.category_filter)

        self.corpus_filter = Corpus(
            id=uuid.uuid4(),
            source_name="test_corpus_filter",
            is_fix=True,
            is_active=True,
            category_id=self.category_filter_id,
        )
        self.test_session.add(self.corpus_filter)
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
    def test_extract_and_with_none_data(self, collector_selector_mock):
        collector_selector_mock.select_collector.return_value = mock.MagicMock(
            spec=IPluginRESTCollector
        )
        self.doc_valid.full_content = None  # Simulate missing content
        collector_selector_mock.select_collector.return_value.run.return_value = [
            WrapperRetrieveDocument(document=self.doc_valid),
        ]

        (
            extracted_docs,
            error_docs,
            process_states,
        ) = document_collector.extract_data_from_urls(
            welearn_documents=[self.doc_valid, self.doc_invalid]
        )

        self.assertEqual(len(extracted_docs), 0)
        self.assertEqual(len(error_docs), 1)
        self.assertEqual(error_docs[0].document_id, self.doc_valid.id)
        self.assertEqual(len(process_states), 1)

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
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.collector_selector"
    )
    def test_extract_data_with_duplicate_traces(self, collector_selector_mock):
        collector_selector_mock.select_collector.return_value = mock.MagicMock(
            spec=IPluginRESTCollector
        )

        duplicate_doc_id = uuid.uuid4()
        duplicate_doc = WeLearnDocument(
            id=duplicate_doc_id,
            url="https://example.org/wiki/Duplicate_trace",
            lang="en",
            full_content=random_string(300),
            description=random_string(100),
            corpus_id=self.corpus_test.id,
            trace=777,
        )
        self.test_session.add(duplicate_doc)
        self.test_session.commit()
        duplicate_doc_db = cast(
            WeLearnDocument,
            self.test_session.query(WeLearnDocument)
            .filter_by(id=duplicate_doc_id)
            .one(),
        )

        self.doc_valid.trace = 777
        collector_selector_mock.select_collector.return_value.run.return_value = [
            WrapperRetrieveDocument(document=self.doc_valid),
            WrapperRetrieveDocument(document=duplicate_doc_db),
        ]

        extracted_docs, error_docs, process_states = (
            document_collector.extract_data_from_urls(
                welearn_documents=[self.doc_valid, duplicate_doc_db]
            )
        )

        self.assertEqual(len(extracted_docs), 1)
        self.assertEqual(extracted_docs[0].id, self.doc_valid.id)
        self.assertEqual(len(error_docs), 1)
        self.assertEqual(error_docs[0].document_id, duplicate_doc_db.id)
        self.assertEqual(
            error_docs[0].error_info,
            "This document got the same trace than another one",
        )
        self.assertEqual(len(process_states), 2)
        self.assertEqual(process_states[0].title, Step.DOCUMENT_SCRAPED.value)
        self.assertEqual(process_states[1].title, Step.DOCUMENT_IS_IRRETRIEVABLE.value)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.collector_selector"
    )
    def test_extract_data_duplicate_trace_with_existing_error(
        self, collector_selector_mock
    ):
        collector_selector_mock.select_collector.return_value = mock.MagicMock(
            spec=IPluginRESTCollector
        )

        second_doc_id = uuid.uuid4()
        second_doc = WeLearnDocument(
            id=second_doc_id,
            url="https://example.org/wiki/Duplicate_trace_with_error",
            lang="en",
            full_content=random_string(300),
            description=random_string(100),
            corpus_id=self.corpus_test.id,
            trace=888,
        )
        self.test_session.add(second_doc)
        self.test_session.commit()
        second_doc_db = cast(
            WeLearnDocument,
            self.test_session.query(WeLearnDocument).filter_by(id=second_doc_id).one(),
        )

        self.doc_valid.trace = 888
        collector_selector_mock.select_collector.return_value.run.return_value = [
            WrapperRetrieveDocument(
                document=self.doc_valid,
                error_info="Timeout during extraction",
                http_error_code=504,
            ),
            WrapperRetrieveDocument(document=second_doc_db),
        ]

        extracted_docs, error_docs, process_states = (
            document_collector.extract_data_from_urls(
                welearn_documents=[self.doc_valid, second_doc_db]
            )
        )

        self.assertEqual(len(extracted_docs), 0)
        self.assertEqual(len(error_docs), 2)
        self.assertTrue(
            any(
                e.document_id == self.doc_valid.id
                and e.error_info == "Timeout during extraction"
                and e.http_error_code == 504
                for e in error_docs
            )
        )
        self.assertTrue(
            any(
                e.document_id == second_doc_db.id
                and e.error_info == "This document got the same trace than another one"
                for e in error_docs
            )
        )
        self.assertEqual(len(process_states), 2)
        self.assertTrue(
            all(s.title == Step.DOCUMENT_IS_IRRETRIEVABLE.value for s in process_states)
        )

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
            full_content="In common usage, randomness is the apparent or actual lack of definite patterns or predictability in information.",
            description="In common usage, randomness",
            corpus_id=self.corpus_test.id,
            details={},
        )

        wd1 = WeLearnDocument(
            id=uuids[1],
            url="https://example.org/wiki/Randomness__2",
            full_content="The fields of mathematics, probability, and statistics use formal definitions of randomness",
            description="The fields of mathematics, probability, and statistics",
            corpus_id=self.corpus_test.id,
            details={},
        )

        self.test_session.add(wd0)
        self.test_session.add(wd1)
        self.test_session.commit()

        # Retrieve ORM instances from the session
        wd0_db = self.test_session.query(WeLearnDocument).filter_by(id=uuids[0]).one()
        wd1_db = self.test_session.query(WeLearnDocument).filter_by(id=uuids[1]).one()

        with (self.path_test_input / "batch_ids.csv").open("w") as f:
            writer = csv.writer(f)
            for uuid_ in uuids:
                writer.writerow([uuid_])

        # Ajout des ProcessState simulés
        process_states = [
            ProcessState(
                id=uuid.uuid4(),
                document_id=wd0_db.id,
                title=Step.DOCUMENT_SCRAPED.value,
            ),
            ProcessState(
                id=uuid.uuid4(),
                document_id=wd1_db.id,
                title=Step.DOCUMENT_SCRAPED.value,
            ),
        ]
        extract_data_mock.return_value = ([wd0_db, wd1_db], [], process_states)

        document_collector.main()

        # Get data from database and check
        for uuid_ in uuids:
            current_doc = cast(
                WeLearnDocument,
                self.test_session.query(WeLearnDocument)
                .filter(WeLearnDocument.id == uuid_)
                .one(),
            )
            self.assertEqual(current_doc.corpus_id, self.corpus_test.id)
            self.assertEqual(current_doc.corpus.source_name, corpus_source_name)

            # Check computed metadata
            self.assertIsInstance(current_doc.lang, str)
            self.assertEqual(current_doc.lang, "en")
            details = current_doc.details or {}
            self.assertIn("duration", details)
            self.assertIn("readability", details)
            self.assertIn("content_and_description_lang", details)

        # Cehck existence of ProcessState
        db_states = list(
            self.test_session.query(ProcessState).filter(
                ProcessState.document_id.in_(uuids)
            )
        )
        self.assertEqual(len(db_states), 2)
        self.assertSetEqual(set([s.document_id for s in db_states]), set(uuids))
        self.assertTrue(all(s.title == Step.DOCUMENT_SCRAPED.value for s in db_states))

    def test_compute_states_and_errors_for_failed_insertion_with_failed_ids(
        self,
    ):
        doc_id = uuid.uuid4()
        document = WeLearnDocument(
            id=doc_id,
            url="https://example.org/wiki/Detached_document",
            full_content="Detached document content",
            description="Detached document description",
            corpus_id=self.corpus_test.id,
            details={},
        )
        self.test_session.add(document)
        self.test_session.commit()

        states = [
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_SCRAPED.value,
            )
        ]
        errors = []

        document_collector.compute_states_and_errors_for_failed_insertion(
            failed_inserted_batch_documents_ids=[doc_id],
            states=states,
            errors=errors,
        )

        self.assertEqual(states[0].title, Step.DOCUMENT_IS_IRRETRIEVABLE.value)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].document_id, doc_id)
        self.assertEqual(errors[0].error_info, "Document is a duplicate")

    # ======================== Tests for filter_on_trace ========================
    # Helper method for filter_on_trace tests

    def _create_document(
        self, trace: int | None = None, url: str = None, doc_id: uuid.UUID = None
    ) -> WeLearnDocument:
        """Helper method to create a WeLearnDocument"""
        return WeLearnDocument(
            id=doc_id or uuid.uuid4(),
            url=url or f"https://example.org/{uuid.uuid4()}",
            lang="en",
            full_content=random_string(100),
            description=random_string(50),
            corpus_id=self.corpus_filter.id,
            trace=trace,
        )

    def test_filter_on_trace_empty_list(self) -> None:
        """Test with empty list of documents"""
        documents = []
        filter_on_trace(documents)
        self.assertEqual(len(documents), 0)

    def test_filter_on_trace_single_document(self) -> None:
        """Test with single document - should not be marked as duplicate"""
        doc = self._create_document(trace=12345)
        wrapper = WrapperRetrieveDocument(document=doc)

        filter_on_trace([wrapper])

        self.assertIsNone(wrapper.error_info)

    def test_filter_on_trace_all_unique_traces(self) -> None:
        """Test with all documents having unique traces"""
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=i))
            for i in range(5)
        ]

        filter_on_trace(wrappers)

        # None should be marked as duplicates
        for wrapper in wrappers:
            self.assertIsNone(wrapper.error_info)

    def test_filter_on_trace_all_same_trace(self) -> None:
        """Test with all documents having the same trace"""
        trace_value = 99999
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=trace_value))
            for _ in range(5)
        ]

        filter_on_trace(wrappers)

        # First one is added to set without duplicate, rest are marked as duplicates
        self.assertIsNone(wrappers[0].error_info)
        for wrapper in wrappers[1:]:
            self.assertEqual(
                wrapper.error_info,
                "This document got the same trace than another one",
            )

    def test_filter_on_trace_partial_duplicates(self) -> None:
        """Test with mix of unique and duplicate traces"""
        # Create documents with traces: 1, 2, 1, 3, 2, 3, 1
        traces = [1, 2, 1, 3, 2, 3, 1]
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=trace))
            for trace in traces
        ]

        filter_on_trace(wrappers)

        # First occurrence of each trace should NOT be marked
        self.assertIsNone(wrappers[0].error_info)  # trace 1, first
        self.assertIsNone(wrappers[1].error_info)  # trace 2, first
        # Duplicates should be marked
        self.assertIsNotNone(wrappers[2].error_info)  # trace 1, duplicate
        self.assertIsNone(wrappers[3].error_info)  # trace 3, first
        self.assertIsNotNone(wrappers[4].error_info)  # trace 2, duplicate
        self.assertIsNotNone(wrappers[5].error_info)  # trace 3, duplicate
        self.assertIsNotNone(wrappers[6].error_info)  # trace 1, duplicate

    def test_filter_on_trace_with_none_trace(self) -> None:
        """Test with documents having None as trace"""
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=None)),
            WrapperRetrieveDocument(document=self._create_document(trace=None)),
            WrapperRetrieveDocument(document=self._create_document(trace=123)),
        ]

        filter_on_trace(wrappers)

        # None traces are treated as duplicates (None == None in set)
        self.assertIsNone(wrappers[0].error_info)  # First None, first occurrence
        self.assertIsNotNone(wrappers[1].error_info)  # Second None, duplicate
        self.assertIsNone(wrappers[2].error_info)  # Unique trace 123

    def test_filter_on_trace_mixed_none_and_values(self) -> None:
        """Test with mix of None and actual trace values"""
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=100)),
            WrapperRetrieveDocument(document=self._create_document(trace=None)),
            WrapperRetrieveDocument(document=self._create_document(trace=100)),
            WrapperRetrieveDocument(document=self._create_document(trace=None)),
            WrapperRetrieveDocument(document=self._create_document(trace=200)),
        ]

        filter_on_trace(wrappers)

        self.assertIsNone(wrappers[0].error_info)  # trace 100, first
        self.assertIsNone(wrappers[1].error_info)  # trace None, first
        self.assertIsNotNone(wrappers[2].error_info)  # trace 100, duplicate
        self.assertIsNotNone(wrappers[3].error_info)  # trace None, duplicate
        self.assertIsNone(wrappers[4].error_info)  # trace 200, first

    def test_filter_on_trace_large_trace_values(self) -> None:
        """Test with very large trace values (BIGINT range)"""
        large_traces = [2**60, 2**62, 2**60, 2**63 - 1]
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=trace))
            for trace in large_traces
        ]

        filter_on_trace(wrappers)

        self.assertIsNone(wrappers[0].error_info)  # 2**60, first
        self.assertIsNone(wrappers[1].error_info)  # 2**62, first
        self.assertIsNotNone(wrappers[2].error_info)  # 2**60, duplicate
        self.assertIsNone(wrappers[3].error_info)  # 2**63-1, first

    def test_filter_on_trace_zero_trace(self) -> None:
        """Test with zero as trace value"""
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=0)),
            WrapperRetrieveDocument(document=self._create_document(trace=0)),
            WrapperRetrieveDocument(document=self._create_document(trace=1)),
            WrapperRetrieveDocument(document=self._create_document(trace=0)),
        ]

        filter_on_trace(wrappers)

        self.assertIsNone(wrappers[0].error_info)  # trace 0, first
        self.assertIsNotNone(wrappers[1].error_info)  # trace 0, duplicate
        self.assertIsNone(wrappers[2].error_info)  # trace 1, first
        self.assertIsNotNone(wrappers[3].error_info)  # trace 0, duplicate

    def test_filter_on_trace_negative_traces(self) -> None:
        """Test with negative trace values"""
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=-100)),
            WrapperRetrieveDocument(document=self._create_document(trace=-100)),
            WrapperRetrieveDocument(document=self._create_document(trace=100)),
        ]

        filter_on_trace(wrappers)

        self.assertIsNone(wrappers[0].error_info)  # -100, first
        self.assertIsNotNone(wrappers[1].error_info)  # -100, duplicate
        self.assertIsNone(wrappers[2].error_info)  # 100, first

    def test_filter_on_trace_preserves_existing_error_info(self) -> None:
        """Test that filter does not overwrite existing error_info"""
        doc1_with_error = self._create_document(trace=123)
        doc2_duplicate = self._create_document(trace=123)

        wrapper1 = WrapperRetrieveDocument(
            document=doc1_with_error,
            error_info="Existing error",
        )
        wrapper2 = WrapperRetrieveDocument(document=doc2_duplicate)

        filter_on_trace([wrapper1, wrapper2])

        # Wrapper1 had error_info before, should still be there
        self.assertEqual(wrapper1.error_info, "Existing error")
        # Wrapper2 is duplicate, gets marked
        self.assertEqual(
            wrapper2.error_info,
            "This document got the same trace than another one",
        )

    def test_filter_on_trace_does_not_add_duplicate_error_on_first_occurrence(
        self,
    ) -> None:
        """Verify first occurrence is never marked as duplicate"""
        # Multiple rounds of same traces
        traces = [777, 777, 777, 777, 777]
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=trace))
            for trace in traces
        ]

        filter_on_trace(wrappers)

        # Only first should NOT have error
        self.assertIsNone(wrappers[0].error_info)
        # All others should have error
        for wrapper in wrappers[1:]:
            self.assertIsNotNone(wrapper.error_info)

    def test_filter_on_trace_order_matters(self) -> None:
        """Test that order of documents matters for which is marked as duplicate"""
        doc_a = self._create_document(trace=555)
        doc_b = self._create_document(trace=555)

        wrappers = [
            WrapperRetrieveDocument(document=doc_a),
            WrapperRetrieveDocument(document=doc_b),
        ]

        filter_on_trace(wrappers)

        # First in order is NOT marked
        self.assertIsNone(wrappers[0].error_info)
        # Second in order IS marked
        self.assertIsNotNone(wrappers[1].error_info)

    def test_filter_on_trace_correct_error_message(self) -> None:
        """Test that duplicate documents get the correct error message"""
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=1)),
            WrapperRetrieveDocument(document=self._create_document(trace=1)),
        ]

        filter_on_trace(wrappers)

        expected_message = "This document got the same trace than another one"
        self.assertEqual(wrappers[1].error_info, expected_message)

    def test_filter_on_trace_many_documents(self) -> None:
        """Test with a large number of documents"""
        num_docs = 1000
        # Create documents with repeating traces
        wrappers = [
            WrapperRetrieveDocument(document=self._create_document(trace=i % 10))
            for i in range(num_docs)
        ]

        filter_on_trace(wrappers)

        # Count how many were marked as duplicates
        duplicates = [w for w in wrappers if w.error_info is not None]
        unique = [w for w in wrappers if w.error_info is None]

        # Should have 10 unique (one per trace value 0-9)
        self.assertEqual(len(unique), 10)
        # Should have num_docs - 10 duplicates
        self.assertEqual(len(duplicates), num_docs - 10)

    def test_filter_on_trace_does_not_modify_document_properties(self) -> None:
        """Test that filter only modifies wrapper.error_info, not document itself"""
        doc = self._create_document(trace=123, url="https://test.com")
        wrapper = WrapperRetrieveDocument(document=doc)

        original_url = wrapper.document.url
        original_trace = wrapper.document.trace
        original_lang = wrapper.document.lang

        filter_on_trace([wrapper])

        # Document properties should remain unchanged
        self.assertEqual(wrapper.document.url, original_url)
        self.assertEqual(wrapper.document.trace, original_trace)
        self.assertEqual(wrapper.document.lang, original_lang)

    def test_filter_on_trace_multiple_calls_are_independent(self) -> None:
        """Test that calling filter_on_trace multiple times produces independent results"""
        doc1 = self._create_document(trace=999)
        doc2 = self._create_document(trace=999)

        # First call
        wrappers_batch1 = [
            WrapperRetrieveDocument(document=doc1),
            WrapperRetrieveDocument(document=doc2),
        ]
        filter_on_trace(wrappers_batch1)

        # Second call with fresh documents
        doc3 = self._create_document(trace=999)
        doc4 = self._create_document(trace=999)
        wrappers_batch2 = [
            WrapperRetrieveDocument(document=doc3),
            WrapperRetrieveDocument(document=doc4),
        ]
        filter_on_trace(wrappers_batch2)

        # Both batches should have same pattern (first not marked, second marked)
        self.assertIsNone(wrappers_batch1[0].error_info)
        self.assertIsNotNone(wrappers_batch1[1].error_info)
        self.assertIsNone(wrappers_batch2[0].error_info)
        self.assertIsNotNone(wrappers_batch2[1].error_info)
