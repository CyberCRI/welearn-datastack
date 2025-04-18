import logging
import os
import uuid
from itertools import groupby
from typing import List, Set
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import DocumentSlice, ProcessState, Sdg
from welearn_datastack.data.enumerations import MLModelsType, Step
from welearn_datastack.modules.retrieve_data_from_database import retrieve_models
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.modules.sdgs_classifiers import (
    bi_classify_slice,
    bi_classify_slices,
    n_classify_slice,
    n_classify_slices,
)
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path
from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError("Log level is not recognized : '%s'", log_level)

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("DocumentClassifier starting...")
    input_artifact = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url json name: %s", input_artifact)

    input_directory, local_artifcat_output = setup_local_path()

    docids = retrieve_ids_from_csv(
        input_artifact=input_artifact, input_directory=input_directory
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve Slices from database
    logger.info("Retrieve Slices from database")
    slices = (
        db_session.query(DocumentSlice)
        .filter(DocumentSlice.document_id.in_(docids))
        .all()
    )
    logger.info("'%s' Slices were retrieved", len(slices))

    bi_models = retrieve_models(docids, db_session, MLModelsType.BI_CLASSIFIER)
    bi_model_by_lang = {x.lang: x.title for x in bi_models}
    logger.info("'%s' Bi-classifier models were retrieved", len(bi_models))

    n_models = retrieve_models(docids, db_session, MLModelsType.N_CLASSIFIER)
    n_model_by_lang = {x.lang: x.title for x in n_models}
    logger.info("'%s' N-classifier models were retrieved", len(n_models))

    # Classify slices
    non_sdg_docs_ids: set[UUID] = set()
    sdg_docs_ids: set[UUID] = set()
    specific_sdgs: List[Sdg] = []
    logger.info("Starting bi-classification")
    key_external_sdg = "external_sdg"
    slices_per_docs = sorted(slices, key=lambda x: x.document_id)  # type: ignore
    for k, g in groupby(slices_per_docs, lambda x: x.document_id):
        doc_slices: List[DocumentSlice] = list(g)  # type: ignore
        lang = doc_slices[0].document.lang
        if not isinstance(lang, str):
            raise ValueError(f"Lang is not a string in slice {doc_slices[0].id}")
        bi_model = bi_model_by_lang.get(lang)
        if not bi_model:
            logger.warning("No bi-classifier model found for document %s", k)
            continue
        logger.info("Bi-classifying document %s with model %s", k, bi_model)

        n_model = n_model_by_lang.get(lang)
        if not n_model:
            logger.warning("No n-classifier model found for document %s", k)
            continue
        logger.info("n-classifying document %s with model %s", k, n_model)

        for s in doc_slices:
            if not isinstance(s.document.details, dict):
                logger.error(f"Details is not a dict in this slice :{s.id}")
                raise ValueError(f"Details is not a dict in this slice :{s.id}")

            externaly_classified_flag = key_external_sdg in s.document.details
            if bi_classify_slice(slice_=s, classifier_model_name=bi_model):
                if externaly_classified_flag:
                    sdg_docs_ids.add(k)
                    for ext_sdg in s.document.details.get(key_external_sdg, []):
                        specific_sdgs.append(
                            Sdg(slice_id=s.id, sdg_number=ext_sdg, id=uuid4())
                        )
                else:
                    specific_sdg = n_classify_slice(
                        _slice=s, classifier_model_name=n_model
                    )
                    if not specific_sdg:
                        non_sdg_docs_ids.add(k)
                        continue
                    specific_sdgs.append(specific_sdg)
                    sdg_docs_ids.add(k)
            else:
                non_sdg_docs_ids.add(k)

    # Delete old slices
    logger.info("Delete old SDGs")
    db_session.query(Sdg).filter(
        Sdg.slice_id.in_([s.slice_id for s in specific_sdgs])
    ).delete()
    db_session.commit()

    # Update SDGs
    logger.info("Updating SDGs")
    db_session.add_all(specific_sdgs)

    # Create process states 0
    logger.info("Creating process states")
    # Create process state for Non sdg docs
    for doc_id in non_sdg_docs_ids:
        db_session.add(
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_CLASSIFIED_NON_SDG.value,
            )
        )

    # Create process state for sdg docs
    for doc_id in sdg_docs_ids:
        db_session.add(
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_CLASSIFIED_SDG.value,
            )
        )
    db_session.commit()
    db_session.close()


if __name__ == "__main__":
    load_dotenv_local()
    main()
