import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

from welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner import main


class TestDocumentCleaner(unittest.TestCase):
    """Test suite for DocumentCleaner module"""

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_main_successful_execution(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that main() executes successfully with all dependencies"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)

        mock_doc_ids = [
            UUID("12345678-1234-5678-1234-567812345678"),
            UUID("87654321-4321-8765-4321-876543218765"),
        ]
        mock_retrieve_ids.return_value = mock_doc_ids

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions
        mock_setup_path.assert_called_once()
        mock_retrieve_ids.assert_called_once_with(
            input_artifact="batch_ids.csv", input_directory=mock_input_dir
        )
        mock_create_session.assert_called_once()
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    @patch.dict("os.environ", {"ARTIFACT_ID_URL_CSV_NAME": "custom_ids.csv"})
    def test_main_with_custom_artifact_name(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that main() uses custom artifact name from environment variable"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)
        mock_retrieve_ids.return_value = [UUID("12345678-1234-5678-1234-567812345678")]

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions
        mock_retrieve_ids.assert_called_once_with(
            input_artifact="custom_ids.csv", input_directory=mock_input_dir
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
    def test_main_with_empty_ids_list(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that main() handles empty document IDs correctly"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)
        mock_retrieve_ids.return_value = []

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions - should still execute without errors
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_main_session_close_on_success(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that the database session is properly closed after successful deletion"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)
        mock_retrieve_ids.return_value = [UUID("12345678-1234-5678-1234-567812345678")]

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions - verify close is called
        mock_session.close.assert_called_once()

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_main_with_multiple_document_ids(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that main() correctly processes multiple document IDs"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)

        # Create multiple UUIDs
        mock_doc_ids = [
            UUID("12345678-1234-5678-1234-567812345678"),
            UUID("87654321-4321-8765-4321-876543218765"),
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        mock_retrieve_ids.return_value = mock_doc_ids

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions
        mock_retrieve_ids.assert_called_once()
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_main_database_session_creation(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that database session is created before operations"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)
        mock_retrieve_ids.return_value = [UUID("12345678-1234-5678-1234-567812345678")]

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions - create_db_session should be called before execute
        mock_create_session.assert_called_once()
        mock_session.execute.assert_called_once()

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_main_commit_before_close(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that session commit is called before close"""
        # Setup
        mock_input_dir = Path("/mock/input/dir")
        mock_setup_path.return_value = (mock_input_dir, None)
        mock_retrieve_ids.return_value = [UUID("12345678-1234-5678-1234-567812345678")]

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Track call order
        call_sequence = []
        mock_session.commit.side_effect = lambda: call_sequence.append("commit")
        mock_session.close.side_effect = lambda: call_sequence.append("close")

        # Execute
        main()

        # Assertions - commit should be called before close
        assert call_sequence == ["commit", "close"]

    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.retrieve_ids_from_csv"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentCleaner.document_cleaner.setup_local_path"
    )
    def test_main_csv_file_loading(
        self, mock_setup_path, mock_retrieve_ids, mock_create_session
    ):
        """Test that CSV file path is correctly constructed and loaded"""
        # Setup
        mock_input_dir = Path("/mock/artifacts")
        mock_setup_path.return_value = (mock_input_dir, None)
        mock_retrieve_ids.return_value = [UUID("12345678-1234-5678-1234-567812345678")]

        mock_session = MagicMock()
        mock_create_session.return_value = mock_session

        # Execute
        main()

        # Assertions - verify retrieve_ids_from_csv is called with correct arguments
        mock_retrieve_ids.assert_called_once_with(
            input_artifact="batch_ids.csv", input_directory=mock_input_dir
        )


if __name__ == "__main__":
    unittest.main()
