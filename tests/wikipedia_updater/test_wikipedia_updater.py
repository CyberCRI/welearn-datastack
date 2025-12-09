import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.modules.wikipedia_updater import is_redirection, is_too_different


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
        result = is_too_different(mock_document)

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
        result = is_too_different(mock_document)

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
            is_too_different(mock_document)

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
            is_too_different(mock_document)

    @patch("welearn_datastack.modules.wikipedia_updater.get_new_https_session")
    def test_is_redirection_true_on_307(self, mock_get_session):
        """Should return True if the first HEAD returns 307 (redirection)."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 307
        mock_response.raise_for_status.return_value = None
        mock_session.head.return_value = mock_response
        mock_get_session.return_value = mock_session
        doc = WeLearnDocument(title="Test_Page", lang="en")
        self.assertTrue(is_redirection(doc))
        mock_session.head.assert_called_once()

    @patch("welearn_datastack.modules.wikipedia_updater.get_new_https_session")
    def test_is_redirection_true_on_301_then_307(self, mock_get_session):
        """Should return True if the first HEAD returns 301 and the second returns 307."""
        mock_session = MagicMock()
        mock_response_301 = MagicMock()
        mock_response_301.status_code = 301
        mock_response_301.raise_for_status.return_value = None
        mock_response_301.headers = {"location": "https://en.wikipedia.org/redirected"}
        mock_response_307 = MagicMock()
        mock_response_307.status_code = 307
        mock_response_307.raise_for_status.return_value = None
        mock_session.head.side_effect = [mock_response_301, mock_response_307]
        mock_get_session.return_value = mock_session
        doc = WeLearnDocument(title="Test_Page", lang="en")
        self.assertTrue(is_redirection(doc))
        self.assertEqual(mock_session.head.call_count, 2)

    @patch("welearn_datastack.modules.wikipedia_updater.get_new_https_session")
    def test_is_redirection_false_on_200(self, mock_get_session):
        """Should return False if the first HEAD returns 200 (no redirection)."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_session.head.return_value = mock_response
        mock_get_session.return_value = mock_session
        doc = WeLearnDocument(title="Test_Page", lang="en")
        self.assertFalse(is_redirection(doc))
        mock_session.head.assert_called_once()

    @patch("welearn_datastack.modules.wikipedia_updater.get_new_https_session")
    def test_is_redirection_false_on_301_then_200(self, mock_get_session):
        """Should return False if the first HEAD returns 301 and the second returns 200 (no redirection)."""
        mock_session = MagicMock()
        mock_response_301 = MagicMock()
        mock_response_301.status_code = 301
        mock_response_301.raise_for_status.return_value = None
        mock_response_301.headers = {"location": "https://en.wikipedia.org/redirected"}
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.raise_for_status.return_value = None
        mock_session.head.side_effect = [mock_response_301, mock_response_200]
        mock_get_session.return_value = mock_session
        doc = WeLearnDocument(title="Test_Page", lang="en")
        self.assertFalse(is_redirection(doc))
        self.assertEqual(mock_session.head.call_count, 2)


if __name__ == "__main__":
    unittest.main()
