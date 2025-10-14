import unittest
from unittest.mock import MagicMock, patch

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.unccelearn_collector import UNCCeLearnURLCollector


class TestUNCCeLearnURLCollector(unittest.TestCase):
    @patch("welearn_datastack.collectors.unccelearn_collector.get_new_https_session")
    def test_collect(self, mock_get_session):
        # Simuler une réponse HTTP
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """
        <div class="courses-list">
            <article class="course-card" data-courseid="219">
                <h3 class="card-title course-name">
                    <a href="https://unccelearn.org/course/view.php?id=219&page=overview">Course 1</a>
                </h3>
            </article>
            <article class="course-card" data-courseid="215">
                <h3 class="card-title course-name">
                    <a href="https://unccelearn.org/course/view.php?id=215&page=overview">Course 2</a>
                </h3>
            </article>
        </div>
        """
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        # Initialiser le collecteur
        corpus = Corpus(id=1, source_name="unccelearn")
        collector = UNCCeLearnURLCollector(corpus=corpus)

        # Appeler la méthode collect
        result = collector.collect()

        # Vérifier les résultats
        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[0].url,
            "https://unccelearn.org/course/view.php?id=219&page=overview&lang=en",
        )
        self.assertEqual(
            result[1].url,
            "https://unccelearn.org/course/view.php?id=215&page=overview&lang=en",
        )
