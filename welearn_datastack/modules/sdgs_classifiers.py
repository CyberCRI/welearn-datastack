import logging
import uuid
from typing import List

import joblib  # type: ignore
import numpy
from sklearn.pipeline import Pipeline

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


def n_classify_slice(
    _slice: DocumentSlice,
    classifier_model_name: str,
    bi_classifier_id: uuid.UUID,
    n_classifier_id: uuid.UUID,
    forced_sdg: None | list = None,
) -> Sdg | None:
    if not forced_sdg:
        forced_sdg = [sdg_n + 1 for sdg_n in range(0, 17)]

    logger.debug("Loading multiclass classifier model %s", classifier_model_name)
    classifier_path = generate_ml_models_path(
        model_type=MLModelsType.N_CLASSIFIER, model_name=classifier_model_name
    )
    classifier_model: Pipeline = joblib.load(classifier_path)
    binary_slice_emb = _slice.embedding
    if not isinstance(binary_slice_emb, bytes):
        raise ValueError(
            f"Embedding must be of type bytes, received type: {type(binary_slice_emb).__name__}"
        )
    # ML
    embedding: numpy.ndarray = numpy.frombuffer(
        bytes(binary_slice_emb), dtype=numpy.float32
    )
    tmp_ds_sdg = classifier_model.predict_proba(embedding.reshape(1, -1))
    ds_sdg = tmp_ds_sdg[0]

    # Prepare probability list for score sort
    proba_lst: list[tuple[int, float]] = [
        (i + 1, proba) for i, proba in enumerate(ds_sdg) if i + 1 in forced_sdg
    ]
    proba_lst.sort(key=lambda x: x[1], reverse=True)

    # If the score is superior to 0.5
    sdg_number = proba_lst[0][0] if proba_lst[0][1] > 0.5 else None
    if sdg_number:
        logger.debug(
            f"Slice {_slice.id} is labelized with SDG {proba_lst[0][0]} with {proba_lst[0][1]} score"
        )
        # Create Sdg object, associating it with the slice and classifiers except if forced_sdg is provided because
        # in this case we assume classification was done outside the pipeline
        return Sdg(
            slice_id=_slice.id,
            sdg_number=sdg_number,
            id=uuid.uuid4(),
            bi_classifier_model_id=bi_classifier_id,
            n_classifier_model_id=n_classifier_id if not forced_sdg else None,
        )
    return None
