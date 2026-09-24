import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from welearn_database.data.models import (
    Base,
    Category,
    Corpus,
    DocumentSlice,
    WeLearnDocument,
)

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner import main


class TestDocumentCleaner(TestCase):
    """Test suite for DocumentCleaner module - tests actual database operations"""

    def setUp(self) -> None:
        """Set up test database and fixtures"""
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

        # Create test category
        self.category_id = uuid.uuid4()
        self.category = Category(id=self.category_id, title="test_category")
        self.test_session.add(self.category)

        # Create test corpus
        self.corpus_id = uuid.uuid4()
        self.corpus = Corpus(
            id=self.corpus_id,
            source_name="test_corpus",
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
        )
        self.test_session.add(self.corpus)

        # Create a test embedding model
        self.embedding_model_id = uuid.uuid4()
        self.test_session.commit()

    def tearDown(self) -> None:
        """Clean up after tests"""
        self.test_session.close()

    def _create_document_with_date(
        self, doc_id: uuid.UUID, created_at: datetime
    ) -> WeLearnDocument:
        """Helper method to create a WeLearnDocument with a specific creation date"""
        doc = WeLearnDocument(
            id=doc_id,
            url=f"https://example.org/doc/{doc_id}",
            corpus_id=self.corpus_id,
            title=f"Test Document {doc_id}",
            lang="en",
            full_content="test content " * 20,  # Ensure minimum length
            description="test description",
            details={"test": "test"},
            created_at=created_at,
        )
        self.test_session.add(doc)
        return doc

    def _create_document_slice(
        self,
        slice_id: uuid.UUID,
        document_id: uuid.UUID,
        slice_content: str,
        order: int = 0,
    ) -> DocumentSlice:
        """Helper method to create a DocumentSlice"""
        slice_obj = DocumentSlice(
            id=slice_id,
            document_id=document_id,
            body=slice_content,
            order_sequence=order,
            embedding_model_name="test-model",
            embedding_model_id=self.embedding_model_id,
        )
        self.test_session.add(slice_obj)
        return slice_obj

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_recent_documents(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of recently created documents (created today)"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create two documents created today
        doc_id_1 = uuid.UUID("12345678-1234-5678-1234-567812345678")
        doc_id_2 = uuid.UUID("87654321-4321-8765-4321-876543218765")

        doc_1 = self._create_document_with_date(doc_id_1, now)
        doc_2 = self._create_document_with_date(doc_id_2, now)

        # Create multiple slices for each document
        slice_1_1 = self._create_document_slice(
            uuid.uuid4(), doc_id_1, "Slice 1 for doc 1", order=0
        )
        slice_1_2 = self._create_document_slice(
            uuid.uuid4(), doc_id_1, "Slice 2 for doc 1", order=1
        )
        slice_2_1 = self._create_document_slice(
            uuid.uuid4(), doc_id_2, "Slice 1 for doc 2", order=0
        )

        self.test_session.commit()

        # Verify slices exist before deletion
        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 3)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = [doc_id_1, doc_id_2]

        # Execute
        main()

        # Verify all slices for the deleted documents are removed
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_old_documents(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of old documents (from 6 months ago)"""
        # Setup
        six_months_ago = datetime.now() - timedelta(days=180)
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents from 6 months ago
        doc_id_1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        doc_id_2 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        doc_id_3 = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

        self._create_document_with_date(doc_id_1, six_months_ago)
        self._create_document_with_date(doc_id_2, six_months_ago)
        self._create_document_with_date(doc_id_3, six_months_ago)

        # Create slices for old documents
        for i, doc_id in enumerate([doc_id_1, doc_id_2, doc_id_3]):
            self._create_document_slice(
                uuid.uuid4(), doc_id, f"Old slice {i} for doc {doc_id}"
            )

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 3)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = [doc_id_1, doc_id_2, doc_id_3]

        # Execute
        main()

        # Verify all old document slices are deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_mixed_age_documents(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of documents with different creation dates"""
        # Setup
        now = datetime.now()
        one_month_ago = now - timedelta(days=30)
        three_months_ago = now - timedelta(days=90)
        one_year_ago = now - timedelta(days=365)

        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents of different ages
        doc_id_recent = uuid.UUID("11111111-1111-1111-1111-111111111111")
        doc_id_1_month = uuid.UUID("22222222-2222-2222-2222-222222222222")
        doc_id_3_months = uuid.UUID("33333333-3333-3333-3333-333333333333")
        doc_id_1_year = uuid.UUID("44444444-4444-4444-4444-444444444444")

        self._create_document_with_date(doc_id_recent, now)
        self._create_document_with_date(doc_id_1_month, one_month_ago)
        self._create_document_with_date(doc_id_3_months, three_months_ago)
        self._create_document_with_date(doc_id_1_year, one_year_ago)

        # Create slices for each document
        doc_ids = [doc_id_recent, doc_id_1_month, doc_id_3_months, doc_id_1_year]
        for doc_id in doc_ids:
            self._create_document_slice(uuid.uuid4(), doc_id, f"Slice for {doc_id}")
            self._create_document_slice(
                uuid.uuid4(), doc_id, f"Another slice for {doc_id}"
            )

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 8)  # 4 docs * 2 slices each

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = doc_ids

        # Execute
        main()

        # Verify all slices are deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_documents_spanning_multiple_years(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of documents spanning multiple years"""
        # Setup
        now = datetime.now()
        one_year_ago = now - timedelta(days=365)
        two_years_ago = now - timedelta(days=730)
        three_years_ago = now - timedelta(days=1095)

        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents from different years
        doc_id_2024 = uuid.UUID("66666666-6666-6666-6666-666666666666")
        doc_id_2023 = uuid.UUID("77777777-7777-7777-7777-777777777777")
        doc_id_2022 = uuid.UUID("88888888-8888-8888-8888-888888888888")
        doc_id_2021 = uuid.UUID("99999999-9999-9999-9999-999999999999")

        self._create_document_with_date(doc_id_2024, now)
        self._create_document_with_date(doc_id_2023, one_year_ago)
        self._create_document_with_date(doc_id_2022, two_years_ago)
        self._create_document_with_date(doc_id_2021, three_years_ago)

        # Create slices for each document
        doc_ids = [doc_id_2024, doc_id_2023, doc_id_2022, doc_id_2021]
        for doc_id in doc_ids:
            self._create_document_slice(
                uuid.uuid4(), doc_id, f"Historical slice for {doc_id}"
            )

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 4)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = doc_ids

        # Execute
        main()

        # Verify all historical slices are deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_single_old_document(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of a single very old document"""
        # Setup
        very_old = datetime.now() - timedelta(days=1825)  # 5 years
        mock_setup_path.return_value = (self.path_test_input, None)

        doc_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        self._create_document_with_date(doc_id, very_old)

        # Create multiple slices for the old document
        self._create_document_slice(uuid.uuid4(), doc_id, "Old slice 1")
        self._create_document_slice(uuid.uuid4(), doc_id, "Old slice 2")
        self._create_document_slice(uuid.uuid4(), doc_id, "Old slice 3")

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 3)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = [doc_id]

        # Execute
        main()

        # Verify all slices for the old document are deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_bulk_documents_same_date(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of bulk documents created on the same date"""
        # Setup
        creation_date = datetime.now() - timedelta(days=60)
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create 10 documents all from the same date
        doc_ids = []
        for i in range(10):
            doc_id = uuid.UUID(f"aaaabbbb-cccc-dddd-eeee-ffff0000{i:04d}")
            doc_ids.append(doc_id)
            self._create_document_with_date(doc_id, creation_date)

            # Each document has 2 slices
            self._create_document_slice(uuid.uuid4(), doc_id, f"Slice 1 for doc {i}")
            self._create_document_slice(uuid.uuid4(), doc_id, f"Slice 2 for doc {i}")

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 20)  # 10 docs * 2 slices

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = doc_ids

        # Execute
        main()

        # Verify all bulk document slices are deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_documents_spanning_one_week(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test deletion of documents created within a one-week span"""
        # Setup
        base_date = datetime.now() - timedelta(days=10)
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents spanning one week
        doc_ids = []
        creation_dates = [
            base_date,  # Day 0
            base_date + timedelta(days=1),  # Day 1
            base_date + timedelta(days=2),  # Day 2
            base_date + timedelta(days=4),  # Day 4
            base_date + timedelta(days=6),  # Day 6
        ]

        for i, creation_date in enumerate(creation_dates):
            doc_id = uuid.UUID(f"11111111-1111-1111-1111-111111{i:06d}")
            doc_ids.append(doc_id)
            self._create_document_with_date(doc_id, creation_date)
            self._create_document_slice(
                uuid.uuid4(), doc_id, f"Slice for doc created on day {i}"
            )

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 5)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = doc_ids

        # Execute
        main()

        # Verify all slices are deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_partial_deletion_only_specified_documents(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that only specified documents are deleted, others remain untouched"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents to delete
        doc_to_delete_1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        doc_to_delete_2 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        # Create documents to keep
        doc_to_keep_1 = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        doc_to_keep_2 = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

        # Add all documents
        self._create_document_with_date(doc_to_delete_1, now)
        self._create_document_with_date(doc_to_delete_2, now - timedelta(days=30))
        self._create_document_with_date(doc_to_keep_1, now - timedelta(days=60))
        self._create_document_with_date(doc_to_keep_2, now - timedelta(days=90))

        # Create slices for all documents
        delete_slice_1_id = uuid.uuid4()
        delete_slice_2_id = uuid.uuid4()
        keep_slice_1_id = uuid.uuid4()
        keep_slice_2_id = uuid.uuid4()

        self._create_document_slice(
            delete_slice_1_id, doc_to_delete_1, "Slice to delete 1"
        )
        self._create_document_slice(
            delete_slice_2_id, doc_to_delete_2, "Slice to delete 2"
        )
        self._create_document_slice(keep_slice_1_id, doc_to_keep_1, "Slice to keep 1")
        self._create_document_slice(keep_slice_2_id, doc_to_keep_2, "Slice to keep 2")

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 4)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = [doc_to_delete_1, doc_to_delete_2]

        # Execute
        main()

        # Verify only specified documents' slices are deleted
        remaining_slices = self.test_session.query(DocumentSlice).all()
        self.assertEqual(len(remaining_slices), 2)

        # Verify the correct slices remain
        remaining_slice_ids = {s.id for s in remaining_slices}
        self.assertIn(keep_slice_1_id, remaining_slice_ids)
        self.assertIn(keep_slice_2_id, remaining_slice_ids)
        self.assertNotIn(delete_slice_1_id, remaining_slice_ids)
        self.assertNotIn(delete_slice_2_id, remaining_slice_ids)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_delete_empty_document_list(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that no slices are deleted when document list is empty"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents that should NOT be deleted
        doc_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        self._create_document_with_date(doc_id, now)
        self._create_document_slice(uuid.uuid4(), doc_id, "Should not be deleted")

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 1)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = []  # Empty list

        # Execute
        main()

        # Verify no slices were deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 1)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_nonexistent_documents_dont_cause_errors(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that trying to delete non-existent documents doesn't cause errors"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create some real documents
        real_doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        self._create_document_with_date(real_doc_id, now)
        self._create_document_slice(uuid.uuid4(), real_doc_id, "Real slice")

        # Create fake IDs that don't exist
        fake_doc_id_1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        fake_doc_id_2 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 1)

        mock_create_db_session.return_value = self.test_session
        # Try to delete mix of real and fake IDs
        mock_retrieve_ids.return_value = [real_doc_id, fake_doc_id_1, fake_doc_id_2]

        # Execute - should not raise an error
        main()

        # Verify only the real document's slices were deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_document_itself_not_deleted_only_slices(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that DocumentCleaner only deletes slices, NOT the WeLearnDocument itself"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create documents with slices
        doc_id_1 = uuid.UUID("12345678-1234-5678-1234-567812345678")
        doc_id_2 = uuid.UUID("87654321-4321-8765-4321-876543218765")

        self._create_document_with_date(doc_id_1, now)
        self._create_document_with_date(doc_id_2, now)

        self._create_document_slice(uuid.uuid4(), doc_id_1, "Slice 1")
        self._create_document_slice(uuid.uuid4(), doc_id_2, "Slice 2")

        self.test_session.commit()

        # Verify initial state
        initial_doc_count = self.test_session.query(WeLearnDocument).count()
        self.assertEqual(initial_doc_count, 2)
        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 2)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = [doc_id_1, doc_id_2]

        # Execute
        main()

        # Verify: Documents should still exist, but slices should be gone
        remaining_docs = self.test_session.query(WeLearnDocument).count()
        self.assertEqual(remaining_docs, 2, "Documents should NOT be deleted!")

        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0, "Slices MUST be deleted!")

        # Verify documents are still accessible
        doc_1 = self.test_session.query(WeLearnDocument).filter_by(id=doc_id_1).first()
        self.assertIsNotNone(doc_1)
        self.assertEqual(doc_1.title, f"Test Document {doc_id_1}")

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_document_without_slices_not_affected(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that documents without slices don't cause issues during cleanup"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create two documents
        doc_with_slices_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        doc_without_slices_id = uuid.UUID("87654321-4321-8765-4321-876543218765")

        self._create_document_with_date(doc_with_slices_id, now)
        self._create_document_with_date(doc_without_slices_id, now)

        # Only add slice to first document
        self._create_document_slice(uuid.uuid4(), doc_with_slices_id, "Slice 1")

        self.test_session.commit()

        initial_doc_count = self.test_session.query(WeLearnDocument).count()
        self.assertEqual(initial_doc_count, 2)
        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, 1)

        mock_create_db_session.return_value = self.test_session
        # Try to delete both documents
        mock_retrieve_ids.return_value = [doc_with_slices_id, doc_without_slices_id]

        # Execute
        main()

        # Verify both documents still exist
        remaining_docs = self.test_session.query(WeLearnDocument).count()
        self.assertEqual(remaining_docs, 2)

        # Verify the slice from doc_with_slices was deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(remaining_slices, 0)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_deletion_count_accuracy(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that the exact number of slices are deleted as expected"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        # Create 5 documents with varying numbers of slices
        docs_and_slice_counts = {
            uuid.UUID("11111111-1111-1111-1111-111111111111"): 3,  # 3 slices
            uuid.UUID("22222222-2222-2222-2222-222222222222"): 5,  # 5 slices
            uuid.UUID("33333333-3333-3333-3333-333333333333"): 1,  # 1 slice
            uuid.UUID("44444444-4444-4444-4444-444444444444"): 2,  # 2 slices
            uuid.UUID("55555555-5555-5555-5555-555555555555"): 4,  # 4 slices
        }

        total_slices_expected = sum(docs_and_slice_counts.values())  # 15

        for doc_id, slice_count in docs_and_slice_counts.items():
            self._create_document_with_date(doc_id, now)
            for i in range(slice_count):
                self._create_document_slice(uuid.uuid4(), doc_id, f"Slice {i+1}")

        self.test_session.commit()

        initial_slice_count = self.test_session.query(DocumentSlice).count()
        self.assertEqual(initial_slice_count, total_slices_expected)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = list(docs_and_slice_counts.keys())

        # Execute
        main()

        # Verify exact count: all 15 slices should be deleted
        remaining_slices = self.test_session.query(DocumentSlice).count()
        self.assertEqual(
            remaining_slices, 0, f"Expected 0 slices, but {remaining_slices} remain"
        )

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_corpus_and_category_remain_intact(
        self, mock_setup_path, mock_retrieve_ids, mock_create_db_session
    ):
        """Test that Corpus and Category remain intact after DocumentCleaner runs"""
        # Setup
        now = datetime.now()
        mock_setup_path.return_value = (self.path_test_input, None)

        doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        self._create_document_with_date(doc_id, now)
        self._create_document_slice(uuid.uuid4(), doc_id, "Slice to delete")

        self.test_session.commit()

        # Verify initial metadata
        initial_corpus = (
            self.test_session.query(Corpus).filter_by(id=self.corpus_id).first()
        )
        initial_category = (
            self.test_session.query(Category).filter_by(id=self.category_id).first()
        )
        self.assertIsNotNone(initial_corpus)
        self.assertIsNotNone(initial_category)

        mock_create_db_session.return_value = self.test_session
        mock_retrieve_ids.return_value = [doc_id]

        # Execute
        main()

        # Verify corpus and category are still there
        remaining_corpus = (
            self.test_session.query(Corpus).filter_by(id=self.corpus_id).first()
        )
        remaining_category = (
            self.test_session.query(Category).filter_by(id=self.category_id).first()
        )

        self.assertIsNotNone(remaining_corpus, "Corpus should not be deleted!")
        self.assertIsNotNone(remaining_category, "Category should not be deleted!")
        self.assertEqual(remaining_corpus.source_name, "test_corpus")
        self.assertEqual(remaining_category.title, "test_category")
