import logging
import math
import os
import re
from functools import cache
from typing import List
from uuid import UUID

import spacy
from sentence_transformers import SentenceTransformer  # type: ignore

from welearn_datastack.data.db_models import DocumentSlice, WeLearnDocument
from welearn_datastack.data.enumerations import MLModelsType
from welearn_datastack.exceptions import NoContent
from welearn_datastack.utils_.path_utils import generate_ml_models_path

logger = logging.getLogger(__name__)

loaded_models: dict[str, SentenceTransformer] = {}


@cache
def _load_spacy_model():
    return spacy.load("xx_sent_ud_sm")


def create_content_slices(
    document: WeLearnDocument, embedding_model_name: str, embedding_model_id: UUID
) -> List[DocumentSlice]:
    """
    Creates slices of the document content and embeds them.
    :return: A list of DocumentSlice objects
    """
    ml_path = generate_ml_models_path(
        model_type=MLModelsType.EMBEDDING,
        model_name=embedding_model_name,  # type: ignore
        extension="",
    )

    if not document.full_content:
        raise NoContent(f"This document is empty {document.id}")

    embedding_model = load_embedding_model(ml_path.as_posix())
    n_splits = math.ceil(
        len(document.full_content) / 1000000
    )  # 1M character is the limit from SpaCy
    split_size = round(len(document.full_content) / n_splits)

    text_content_slices = []
    for i in range(0, n_splits):
        text_content_slices += _split_by_word_respecting_sent_boundary(
            slice_length=embedding_model.get_max_seq_length(),  # type: ignore
            document_content=document.full_content[i * split_size : (i + 1) * split_size],  # type: ignore
            document_lang=document.lang,  # type: ignore
        )

    slices: List[DocumentSlice] = []

    embeddings = embedding_model.encode(
        text_content_slices, device=os.environ.get("ST_DEVICE", "")
    )

    # Create Slices objects
    for i, (text, embedding) in enumerate(zip(text_content_slices, embeddings)):
        slices.append(
            DocumentSlice(
                embedding=embedding.tobytes(),
                body=text,
                order_sequence=i,
                embedding_model_name=embedding_model_name,
                document_id=document.id,
                embedding_model_id=embedding_model_id,
            )
        )
    return slices


def load_embedding_model(str_path: str) -> SentenceTransformer:
    """
    Loads the embedding model for the document language
    :param str_path: The path to the embedding model
    :return: The embedding model
    """
    logger.info("Loading embedding model from %s", str_path)

    device = os.environ.get("ST_DEVICE", None)
    backend = os.environ.get("ST_BACKEND", None)
    logger.info("ST_DEVICE: %s", device)
    logger.info("ST_BACKEND: %s", backend)

    if device not in ["cpu", "cuda", None]:
        raise ValueError("ST_DEVICE must be one of 'cpu', 'cuda' or None")

    if not isinstance(backend, str) and backend not in ["torch", "onnx", "openvino"]:
        raise ValueError("ST_BACKEND must be one of 'torch', 'onnx' or 'openvino'")

    model = loaded_models.get(str_path, None)
    if model is not None:
        logger.info("%s Model already loaded", str_path)
        return model

    logger.info("%s Model not loaded yet", str_path)
    loaded_models[str_path] = SentenceTransformer(
        model_name_or_path=str_path,
        device=device,
        backend=backend,  # type: ignore
    )
    return loaded_models[str_path]


def _split_by_word_respecting_sent_boundary(
    document_content: str,
    document_lang: str,
    slice_length: int,
) -> List[str]:
    """
    Splits the text into slices of slice_length words while respecting sentence boundaries.

    :param document_content: The text to split into slices
    :param lang: The language of the text in format 'en', 'fr', 'es', etc.
    :param slice_length:  The maximum number of words in a slice
    :return: Slices of text with a maximum of slice_length words
    """
    logger.info("Splitting document into slices of %d words", slice_length)
    text = re.sub(" +", " ", re.sub(r"\n+", " ", document_content)).strip()

    nlp_model = _load_spacy_model()
    spacy_doc = nlp_model(text)

    word_count_slice = 0
    list_slices = []
    current_slice: List[str] = []

    for span_sentence in spacy_doc.sents:
        sentence = span_sentence.text.strip()
        word_count_sen = len(sentence.split())

        if word_count_sen > slice_length:
            # Number of words in a single sentence exceeds slice_length -> truncate sentence
            sentence = " ".join(sentence.split()[: slice_length - 1]) + "..."
            word_count_sen = len(sentence.split())

        if word_count_slice + word_count_sen > slice_length:
            # Number of words exceeds slice_length -> save current slice and start a new one
            if current_slice:
                list_slices.append(current_slice)
            current_slice = []
            word_count_slice = 0

        current_slice.append(sentence)
        word_count_slice += word_count_sen

    if current_slice:
        list_slices.append(current_slice)

    text_slices = []
    for _slice in list_slices:
        txt = " ".join(_slice)
        if len(txt) > 0:
            text_slices.append(txt)

    logger.info("Split document into %d slices", len(text_slices))
    return text_slices
