import logging
from typing import List

from keybert import KeyBERT  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore
from spacy.lang.en import English
from spacy.lang.fr import French

from welearn_datastack.data.db_models import WeLearnDocument
from welearn_datastack.data.enumerations import MLModelsType
from welearn_datastack.modules.embedding_model_helpers import (
    get_document_embedding_model_name_from_lang,
    load_embedding_model,
)
from welearn_datastack.utils_.path_utils import generate_ml_models_path

logger = logging.getLogger(__name__)

loaded_models: dict[str, SentenceTransformer] = {}

en_nlp = English()
fr_nlp = French()


def _get_nlp_model(language: str):
    if language == "en":
        return en_nlp
    elif language == "fr":
        return fr_nlp
    else:
        raise ValueError(f"Unsupported language: {language}")


def extract_keywords(document: WeLearnDocument) -> List[str]:
    """
    Extract keywords from a document description
    """
    ml_path = generate_ml_models_path(
        model_type=MLModelsType.EMBEDDING,
        model_name=get_document_embedding_model_name_from_lang(lang=document.lang),  # type: ignore
        extension="",
    )
    embedding_model = load_embedding_model(ml_path.as_posix())
    kw_model = KeyBERT(model=embedding_model)

    nlp_model = _get_nlp_model(str(document.lang))

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
