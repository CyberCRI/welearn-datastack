import unittest
from unittest.mock import Mock, patch

import numpy

from welearn_datastack.data.db_models import DocumentSlice, Sdg
from welearn_datastack.modules.sdgs_classifiers import (
    bi_classify_slices,
    n_classify_slice,
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
    def test_should_classify_slices_n_with_force_sdg(self, mock_load):
        mock_load.return_value.predict_proba.return_value = [
            numpy.array(
                [0.3, 0.2, 0.99, 0.562, 0.2, 0.1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            )
        ]
        slice = DocumentSlice(id=1, embedding=b"\x00" * 128)
        result = n_classify_slice(slice, "model_name", forced_sdg=[4, 5, 10, 11, 12])
        self.assertEqual(result.sdg_number, 4)

    @patch("joblib.load")
    def test_should_not_classify_slices_n_with_force_sdg(self, mock_load):
        mock_load.return_value.predict_proba.return_value = [
            numpy.array(
                [0.3, 0.2, 0.99, 0.562, 0.2, 0.1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            )
        ]
        slice = DocumentSlice(id=1, embedding=b"\x00" * 128)
        result = n_classify_slice(slice, "model_name", forced_sdg=[1, 11, 12])
        self.assertEqual(result, None)

    @patch("joblib.load")
    def test_should_classify_slices_n(self, mock_load):
        mock_load.return_value.predict_proba.return_value = [
            numpy.array(
                [0.3, 0.2, 0.99, 0.562, 0.2, 0.1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            )
        ]
        slice = DocumentSlice(id=1, embedding=b"\x00" * 128)
        result = n_classify_slice(slice, "model_name")
        self.assertEqual(result.sdg_number, 3)

    @patch("joblib.load")
    def test_should_not_classify_slices_n(self, mock_load):
        mock_load.return_value.predict_proba.return_value = [numpy.array([0, 0, 0])]
        slice = DocumentSlice(id=1, embedding=b"\x00" * 128)
        result = n_classify_slice(slice, "model_name")
        self.assertEqual(result, None)
