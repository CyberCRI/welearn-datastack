from unittest import TestCase
from unittest.mock import MagicMock, patch

from welearn_datastack.data.enumerations import URLStatus
from welearn_datastack.modules.url_checker import check_url


class Test(TestCase):
    def setUp(self):
        self.url_1 = "https://www.example.org/in_c1"
        self.url_2 = "https://www.example.org/in_c2"
        self.url_3 = "https://www.example.org/in_c3"

    @patch("welearn_datastack.modules.url_checker.get_new_https_session")
    def test_check_url(self, mock_get_new_https_session):
        """
        Test that the URL is correctly checked
        """
        ret = MagicMock().get = MagicMock()
        mock_get_new_https_session.return_value.get.return_value = ret

        mock_get_new_https_session.return_value.get.return_value.status_code = 200
        self.assertEqual((URLStatus.VALID, 200), check_url(self.url_1))

        mock_get_new_https_session.return_value.get.return_value.status_code = 301
        self.assertEqual((URLStatus.UPDATE, 301), check_url(self.url_2))

        mock_get_new_https_session.return_value.get.return_value.status_code = 404
        self.assertEqual((URLStatus.DELETE, 404), check_url(self.url_3))
