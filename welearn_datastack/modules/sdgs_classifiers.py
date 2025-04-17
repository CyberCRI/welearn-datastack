import logging
import uuid
from typing import List

import joblib  # type: ignore
import numpy

from welearn_datastack.data.db_models import DocumentSlice, Sdg
from welearn_datastack.data.enumerations import MLModelsType
from welearn_datastack.utils_.path_utils import generate_ml_models_path

logger = logging.getLogger(__name__)


def bi_classify_slices(slices: List[DocumentSlice], classifier_model_name: str) -> bool:
    """
    Bi classifier for welearn sliced containers
    :param classifier_model_name:  The name of the classifier model, wich also the name of the file
    :param slices: Input of welearn sliced containers
    :return: True if SDG, False otherwise
    """
    for _slice in slices:
        if bi_classify_slice(
            slice_=_slice, classifier_model_name=classifier_model_name
        ):
            return True
    return False


def bi_classify_slice(slice_: DocumentSlice, classifier_model_name: str) -> bool:
    # Load model
    logger.debug("Loading classifier model %s", classifier_model_name)
    classifier_path = generate_ml_models_path(
        model_type=MLModelsType.BI_CLASSIFIER, model_name=classifier_model_name
    )
    classifier_model = joblib.load(classifier_path)
    # ML
    embedding: numpy.ndarray = numpy.frombuffer(
        bytes(slice_.embedding), dtype=numpy.float32  # type: ignore
    )
    ds_sdg = bool(classifier_model.predict(embedding.reshape(1, -1)))
    if ds_sdg:
        return True
    return False


def n_classify_slices(
    slices: List[DocumentSlice], classifier_model_name: str
) -> List[Sdg]:
    """
    Classify a list of slices of a document
    :param slices: Slices of a document
    :param classifier_model_name: Name of the classifier to use to classify the slices
    :return: List of DocumentSlice with SDGs they belong to updated
    """
    # Load model
    doc_sdgs = []

    for _slice in slices:
        ret_sdg = n_classify_slice(
            _slice=_slice, classifier_model_name=classifier_model_name
        )
        if ret_sdg:
            doc_sdgs.append(ret_sdg)

    return doc_sdgs


def n_classify_slice(_slice: DocumentSlice, classifier_model_name: str) -> Sdg | None:
    logger.debug("Loading multiclass classifier model %s", classifier_model_name)
    classifier_path = generate_ml_models_path(
        model_type=MLModelsType.N_CLASSIFIER, model_name=classifier_model_name
    )
    classifier_model = joblib.load(classifier_path)
    binary_slice_emb = _slice.embedding
    if not isinstance(binary_slice_emb, bytes):
        raise ValueError(
            f"Embedding must be of type bytes, received type: {type(binary_slice_emb).__name__}"
        )
    # ML
    embedding: numpy.ndarray = numpy.frombuffer(
        bytes(binary_slice_emb), dtype=numpy.float32
    )
    tmp_ds_sdg = classifier_model.predict(embedding.reshape(1, -1))
    ds_sdg = tmp_ds_sdg[0]
    logger.debug("Slice classified as SDG: %s", ds_sdg)
    if ds_sdg.sum() == 1:
        ret = ds_sdg.argmax() + 1
        try:
            ret = int(ret)
            return Sdg(slice_id=_slice.id, sdg_number=ret, id=uuid.uuid4())
        except ValueError:
            logger.error("SDG is not an integer: %s", ret)
    return None
