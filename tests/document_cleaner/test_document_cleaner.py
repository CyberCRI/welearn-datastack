import csv
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from welearn_database.data.enumeration import Step
from welearn_database.data.models import (
    Base,
    Category,
    Corpus,
    DocumentSlice,
    ProcessState,
    WeLearnDocument,
)

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner import main


class TestDocumentCleanerUnit(TestCase):
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    def test_main_adds_document_cleaned_process_state_only_for_existing_documents(
        self,
        mock_create_db_session,
        mock_retrieve_ids_from_csv,
        mock_setup_local_path,
    ):
        mock_input_directory = "unit_test_input_directory"
        mock_output_directory = "unit_test_output_directory"
        existing_doc_id_1 = uuid.uuid4()
        existing_doc_id_2 = uuid.uuid4()
        missing_doc_id = uuid.uuid4()

        db_session = Mock()
        query = Mock()
        filtered_query = Mock()
        mock_create_db_session.return_value = db_session
        mock_setup_local_path.return_value = (
            mock_input_directory,
            mock_output_directory,
        )
        mock_retrieve_ids_from_csv.return_value = [
            existing_doc_id_1,
            missing_doc_id,
            existing_doc_id_2,
        ]
        db_session.query.return_value = query
        query.filter.return_value = filtered_query
        filtered_query.all.return_value = [
            (existing_doc_id_1,),
            (existing_doc_id_2,),
        ]

        main()

        mock_retrieve_ids_from_csv.assert_called_once_with(
            input_artifact="batch_ids.csv",
            input_directory=mock_input_directory,
        )
        db_session.execute.assert_called_once()
        self.assertEqual(db_session.add.call_count, 2)

        added_states = [call.args[0] for call in db_session.add.call_args_list]
        self.assertTrue(all(isinstance(state, ProcessState) for state in added_states))
        self.assertEqual(
            [state.document_id for state in added_states],
            [existing_doc_id_1, existing_doc_id_2],
        )
        self.assertTrue(all(state.id is not None for state in added_states))
        self.assertEqual(
            [state.title for state in added_states],
            [Step.DOCUMENT_CLEANED.value, Step.DOCUMENT_CLEANED.value],
        )
        self.assertNotIn(missing_doc_id, [state.document_id for state in added_states])
        db_session.commit.assert_called_once_with()
        db_session.close.assert_called_once_with()

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    def test_main_does_not_add_process_state_when_csv_is_empty(
        self,
        mock_create_db_session,
        mock_retrieve_ids_from_csv,
        mock_setup_local_path,
    ):
        mock_input_directory = "unit_test_input_directory"
        mock_output_directory = "unit_test_output_directory"
        db_session = Mock()
        query = Mock()
        filtered_query = Mock()
        mock_create_db_session.return_value = db_session
        mock_setup_local_path.return_value = (
            mock_input_directory,
            mock_output_directory,
        )
        mock_retrieve_ids_from_csv.return_value = []
        db_session.query.return_value = query
        query.filter.return_value = filtered_query
        filtered_query.all.return_value = []

        main()

        db_session.execute.assert_called_once()
        db_session.add.assert_not_called()
        db_session.commit.assert_called_once_with()
        db_session.close.assert_called_once_with()


class TestDocumentCleaner(TestCase):
    """Integration tests for DocumentCleaner using a real SQLite database."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.input_path = self.root_path / "input"
        self.output_path = self.root_path / "output"
        self.input_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.root_path / "document_cleaner.db"

        os.environ["IS_LOCAL"] = ""
        os.environ["ARTIFACT_ROOT"] = self.root_path.as_posix()
        os.environ["ARTIFACT_INPUT_FOLDER_NAME"] = "input"
        os.environ["ARTIFACT_OUTPUT_FOLDER_NAME"] = "output"
        os.environ.pop("ARTIFACT_ID_URL_CSV_NAME", None)
        os.environ["PG_DRIVER"] = "sqlite"
        os.environ.pop("PG_USER", None)
        os.environ.pop("PG_PASSWORD", None)
        os.environ.pop("PG_HOST", None)
        os.environ.pop("PG_PORT", None)
        os.environ["PG_DB"] = self.db_path.as_posix()

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        handle_schema_with_sqlite(self.engine)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        seed_session = self.SessionLocal()
        self.category_id = uuid.uuid4()
        self.corpus_id = uuid.uuid4()
        seed_session.add(Category(id=self.category_id, title="test_category"))
        seed_session.add(
            Corpus(
                id=self.corpus_id,
                source_name="test_corpus",
                is_fix=True,
                is_active=True,
                category_id=self.category_id,
            )
        )
        seed_session.commit()
        seed_session.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_document(
        self, session, doc_id: uuid.UUID, created_at: datetime
    ) -> None:
        session.add(
            WeLearnDocument(
                id=doc_id,
                url=f"https://example.org/{doc_id}",
                corpus_id=self.corpus_id,
                title=f"Document {doc_id}",
                lang="en",
                full_content="test content " * 20,
                description="test description",
                details={"source": "test"},
                created_at=created_at,
            )
        )

    def _create_slice(
        self,
        session,
        slice_id: uuid.UUID,
        document_id: uuid.UUID,
        body: str,
        order_sequence: int = 0,
    ) -> None:
        session.add(
            DocumentSlice(
                id=slice_id,
                document_id=document_id,
                body=body,
                order_sequence=order_sequence,
                embedding_model_name="test-model",
                embedding_model_id=uuid.uuid4(),
            )
        )

    def _write_ids_csv(self, filename: str, ids: list[uuid.UUID]) -> Path:
        file_path = self.input_path / filename
        with file_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            for doc_id in ids:
                writer.writerow([str(doc_id)])
        return file_path

    def _get_session(self):
        return self.SessionLocal()

    def _get_process_states(self, session):
        return session.query(ProcessState).order_by(ProcessState.created_at.asc()).all()

    def _run_main_with_session(self, session) -> None:
        with patch(
            "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session",
            return_value=session,
        ):
            main()

    def test_delete_recent_documents_from_real_csv_and_db(self):
        session = self._get_session()
        now = datetime.now()
        doc_ids = [uuid.uuid4(), uuid.uuid4()]

        for index, doc_id in enumerate(doc_ids):
            self._create_document(session, doc_id, now - timedelta(days=index))
            self._create_slice(session, uuid.uuid4(), doc_id, f"slice-{index}-0", 0)
            self._create_slice(session, uuid.uuid4(), doc_id, f"slice-{index}-1", 1)

        session.commit()
        session.close()

        self._write_ids_csv("batch_ids.csv", doc_ids)

        self._run_main_with_session(self._get_session())

        verify_session = self._get_session()
        self.assertEqual(verify_session.query(DocumentSlice).count(), 0)
        self.assertEqual(verify_session.query(WeLearnDocument).count(), 2)
        process_states = self._get_process_states(verify_session)
        self.assertEqual(len(process_states), 2)
        self.assertSetEqual(
            {state.document_id for state in process_states},
            set(doc_ids),
        )
        self.assertTrue(
            all(state.title == Step.DOCUMENT_CLEANED.value for state in process_states)
        )
        verify_session.close()

    def test_delete_documents_of_different_dates_using_real_db(self):
        session = self._get_session()
        now = datetime.now()

        doc_ids_to_delete = [
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ]
        dates = [now, now - timedelta(days=30), now - timedelta(days=365)]

        for doc_id, created_at in zip(doc_ids_to_delete, dates, strict=True):
            self._create_document(session, doc_id, created_at)
            self._create_slice(session, uuid.uuid4(), doc_id, f"slice-{doc_id}")
            self._create_slice(session, uuid.uuid4(), doc_id, f"slice-2-{doc_id}")

        remaining_doc_id = uuid.uuid4()
        self._create_document(session, remaining_doc_id, now - timedelta(days=10))
        self._create_slice(session, uuid.uuid4(), remaining_doc_id, "keep-me")

        session.commit()
        session.close()

        self._write_ids_csv("batch_ids.csv", doc_ids_to_delete)

        self._run_main_with_session(self._get_session())

        verify_session = self._get_session()
        remaining_docs = verify_session.query(WeLearnDocument).all()
        remaining_slices = verify_session.query(DocumentSlice).all()

        self.assertEqual(len(remaining_docs), 4)
        self.assertEqual(len(remaining_slices), 1)
        self.assertEqual(remaining_slices[0].document_id, remaining_doc_id)
        process_states = self._get_process_states(verify_session)
        self.assertEqual(len(process_states), 3)
        self.assertSetEqual(
            {state.document_id for state in process_states},
            set(doc_ids_to_delete),
        )
        self.assertTrue(
            all(state.title == Step.DOCUMENT_CLEANED.value for state in process_states)
        )
        verify_session.close()

    def test_delete_only_matching_ids_and_keep_others(self):
        session = self._get_session()
        now = datetime.now()

        delete_doc_ids = [uuid.uuid4(), uuid.uuid4()]
        keep_doc_ids = [uuid.uuid4(), uuid.uuid4()]

        for doc_id in delete_doc_ids:
            self._create_document(session, doc_id, now - timedelta(days=15))
            self._create_slice(session, uuid.uuid4(), doc_id, f"delete-{doc_id}")

        for doc_id in keep_doc_ids:
            self._create_document(session, doc_id, now - timedelta(days=45))
            self._create_slice(session, uuid.uuid4(), doc_id, f"keep-{doc_id}")
            self._create_slice(session, uuid.uuid4(), doc_id, f"keep-{doc_id}-2", 1)

        session.commit()
        session.close()

        self._write_ids_csv("batch_ids.csv", delete_doc_ids)

        self._run_main_with_session(self._get_session())

        verify_session = self._get_session()
        remaining_slices = verify_session.query(DocumentSlice).all()
        remaining_doc_ids = {slice_.document_id for slice_ in remaining_slices}

        self.assertEqual(len(remaining_slices), 4)
        self.assertSetEqual(remaining_doc_ids, set(keep_doc_ids))
        self.assertEqual(verify_session.query(WeLearnDocument).count(), 4)
        process_states = self._get_process_states(verify_session)
        self.assertEqual(len(process_states), 2)
        self.assertSetEqual(
            {state.document_id for state in process_states},
            set(delete_doc_ids),
        )
        self.assertTrue(
            all(state.title == Step.DOCUMENT_CLEANED.value for state in process_states)
        )
        verify_session.close()

    def test_nonexistent_ids_in_csv_are_ignored(self):
        session = self._get_session()
        now = datetime.now()

        real_doc_id = uuid.uuid4()
        self._create_document(session, real_doc_id, now)
        self._create_slice(session, uuid.uuid4(), real_doc_id, "real-slice")
        session.commit()
        session.close()

        fake_doc_id = uuid.uuid4()
        self._write_ids_csv("batch_ids.csv", [real_doc_id, fake_doc_id])

        self._run_main_with_session(self._get_session())

        verify_session = self._get_session()
        self.assertEqual(verify_session.query(DocumentSlice).count(), 0)
        self.assertEqual(verify_session.query(WeLearnDocument).count(), 1)
        process_states = self._get_process_states(verify_session)
        self.assertEqual(len(process_states), 1)
        self.assertEqual(process_states[0].document_id, real_doc_id)
        self.assertEqual(process_states[0].title, Step.DOCUMENT_CLEANED.value)
        verify_session.close()

    def test_empty_csv_does_not_delete_anything(self):
        session = self._get_session()
        now = datetime.now()
        doc_id = uuid.uuid4()
        self._create_document(session, doc_id, now)
        self._create_slice(session, uuid.uuid4(), doc_id, "keep-this")
        session.commit()
        session.close()

        self._write_ids_csv("batch_ids.csv", [])

        self._run_main_with_session(self._get_session())

        verify_session = self._get_session()
        self.assertEqual(verify_session.query(DocumentSlice).count(), 1)
        self.assertEqual(verify_session.query(WeLearnDocument).count(), 1)
        self.assertEqual(self._get_process_states(verify_session), [])
        verify_session.close()

    def test_custom_csv_filename_is_respected(self):
        session = self._get_session()
        now = datetime.now()
        doc_id = uuid.uuid4()
        self._create_document(session, doc_id, now)
        self._create_slice(session, uuid.uuid4(), doc_id, "custom-file-slice")
        session.commit()
        session.close()

        os.environ["ARTIFACT_ID_URL_CSV_NAME"] = "custom_ids.csv"
        self._write_ids_csv("custom_ids.csv", [doc_id])

        try:
            self._run_main_with_session(self._get_session())
        finally:
            os.environ.pop("ARTIFACT_ID_URL_CSV_NAME", None)

        verify_session = self._get_session()
        self.assertEqual(verify_session.query(DocumentSlice).count(), 0)
        process_states = self._get_process_states(verify_session)
        self.assertEqual(len(process_states), 1)
        self.assertEqual(process_states[0].document_id, doc_id)
        self.assertEqual(process_states[0].title, Step.DOCUMENT_CLEANED.value)
        verify_session.close()
