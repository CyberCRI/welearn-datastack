import unittest
from unittest.mock import Mock, patch

import numpy

from welearn_datastack.data.db_models import DocumentSlice, Sdg
from welearn_datastack.modules.sdgs_classifiers import (
    bi_classify_slices,
    n_classify_slices,
)


class TestSdgsClassifiers(unittest.TestCase):
    @patch("joblib.load")
    def test_should_classify_slices_bi(self, mock_load):
        mock_load.return_value.predict.return_value = True
        slices = [DocumentSlice(embedding=b"\x00" * 128)]
        result = bi_classify_slices(slices, "model_name")
        self.assertTrue(result)

    @patch("joblib.load")
    def test_should_not_classify_slices_bi(self, mock_load):
        mock_load.return_value.predict.return_value = False
        slices = [DocumentSlice(embedding=b"\x00" * 128)]
        result = bi_classify_slices(slices, "model_name")
        self.assertFalse(result)

    @patch("joblib.load")
    def test_should_classify_slices_n(self, mock_load):
        mock_load.return_value.predict.return_value = [numpy.array([0, 1, 0])]
        slices = [DocumentSlice(id=1, embedding=b"\x00" * 128)]
        result = n_classify_slices(slices, "model_name")
        self.assertEqual(result[0].sdg_number, 2)

    @patch("joblib.load")
    def test_should_not_classify_slices_n(self, mock_load):
        mock_load.return_value.predict.return_value = [numpy.array([0, 0, 0])]
        slices = [DocumentSlice(id=1, embedding=b"\x00" * 128)]
        result = n_classify_slices(slices, "model_name")
        self.assertEqual(result, [])
