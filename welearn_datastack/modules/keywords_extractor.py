import logging
from functools import cache
from typing import List

import spacy
from keybert import KeyBERT  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore

from welearn_datastack.data.db_models import WeLearnDocument
from welearn_datastack.data.enumerations import MLModelsType
from welearn_datastack.modules.embedding_model_helpers import load_embedding_model
from welearn_datastack.utils_.path_utils import generate_ml_models_path

logger = logging.getLogger(__name__)

loaded_models: dict[str, SentenceTransformer] = {}


@cache
def _load_model():
    return spacy.load("xx_sent_ud_sm")


def extract_keywords(
    document: WeLearnDocument, embedding_model_name_from_db: str
) -> List[str]:
    """
    Extract keywords from a document description
    """
    ml_path = generate_ml_models_path(
        model_type=MLModelsType.EMBEDDING,
        model_name=embedding_model_name_from_db,
        extension="",
    )
    embedding_model = load_embedding_model(ml_path.as_posix())
    kw_model = KeyBERT(model=embedding_model)

    nlp_model = _load_model()
    doc = nlp_model(str(document.description))
    clean_description = " ".join(
        [token.text for token in [tk for tk in doc if not tk.is_stop]]
    )
    keywords = kw_model.extract_keywords(
        clean_description,
        keyphrase_ngram_range=(1, 2),
        stop_words=[],
        use_mmr=True,
        diversity=0.7,
    )
    keywords = [kw[0] for kw in keywords if kw[1] > 0.5]
    return keywords
