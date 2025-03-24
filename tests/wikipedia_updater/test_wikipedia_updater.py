import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from welearn_datastack.data.db_models import WeLearnDocument
from welearn_datastack.modules.wikipedia_updater import compare_with_current_version


class TestWikipediaUpdater(unittest.TestCase):
    @patch("welearn_datastack.modules.wikipedia_updater.requests.Session")
    @patch("welearn_datastack.modules.wikipedia_updater._get_revision_id")
    def test_compare_with_current_version_size_difference_exceeds_threshold(
        self, mock_get_revision_id, mock_session
    ):
        # Mock the revision ID
        mock_get_revision_id.return_value = "12345"

        # Mock the session's GET request
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.get.return_value.json.return_value = {
            "compare": {
                "fromsize": 1000,
                "diffsize": 60,  # 6% difference
            }
        }

        # Create a mock document
        mock_document = WeLearnDocument(
            title="Test_Page",
            lang="en",
            updated_at=datetime(2023, 1, 1),
        )

        # Call the function
        result = compare_with_current_version(mock_document)

        # Assertions
        mock_get_revision_id.assert_called_once_with(
            mock_session_instance, "Test_Page", datetime(2023, 1, 1), "en"
        )
        mock_session_instance.get.assert_called_once()
        self.assertTrue(result)

    @patch("welearn_datastack.modules.wikipedia_updater.requests.Session")
    @patch("welearn_datastack.modules.wikipedia_updater._get_revision_id")
    def test_compare_with_current_version_size_difference_below_threshold(
        self, mock_get_revision_id, mock_session
    ):
        # Mock the revision ID
        mock_get_revision_id.return_value = "12345"

        # Mock the session's GET request
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.get.return_value.json.return_value = {
            "compare": {
                "fromsize": 1000,
                "diffsize": 40,  # 4% difference
            }
        }

        # Create a mock document
        mock_document = WeLearnDocument(
            title="Test_Page",
            lang="en",
            updated_at=datetime(2023, 1, 1),
        )

        # Call the function
        result = compare_with_current_version(mock_document)

        # Assertions
        mock_get_revision_id.assert_called_once_with(
            mock_session_instance, "Test_Page", datetime(2023, 1, 1), "en"
        )
        mock_session_instance.get.assert_called_once()
        self.assertFalse(result)

    @patch("welearn_datastack.modules.wikipedia_updater.requests.Session")
    @patch("welearn_datastack.modules.wikipedia_updater._get_revision_id")
    def test_compare_with_current_version_key_error(
        self, mock_get_revision_id, mock_session
    ):
        # Mock the revision ID
        mock_get_revision_id.return_value = "12345"

        # Mock the session's GET request with missing keys
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.get.return_value.json.return_value = {"compare": {}}

        # Create a mock document
        mock_document = WeLearnDocument(
            title="Test_Page",
            lang="en",
            updated_at=datetime(2023, 1, 1),
        )

        # Call the function and expect a KeyError
        with self.assertRaises(KeyError):
            compare_with_current_version(mock_document)

    @patch("welearn_datastack.modules.wikipedia_updater.requests.Session")
    @patch("welearn_datastack.modules.wikipedia_updater._get_revision_id")
    def test_compare_with_current_version_request_exception(
        self, mock_get_revision_id, mock_session
    ):
        # Mock the revision ID
        mock_get_revision_id.return_value = "12345"

        # Mock the session's GET request to raise an exception
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.get.side_effect = Exception("Request failed")

        # Create a mock document
        mock_document = WeLearnDocument(
            title="Test_Page",
            lang="en",
            updated_at=datetime(2023, 1, 1),
        )

        # Call the function and expect an exception
        with self.assertRaises(Exception):
            compare_with_current_version(mock_document)


if __name__ == "__main__":
    unittest.main()
