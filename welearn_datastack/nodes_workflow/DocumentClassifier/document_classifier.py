import logging
import os
import uuid
from itertools import groupby
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import DocumentSlice, ProcessState, Sdg
from welearn_datastack.data.enumerations import MLModelsType, Step
from welearn_datastack.modules.retrieve_data_from_database import retrieve_models
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.modules.sdgs_classifiers import (
    bi_classify_slice,
    n_classify_slice,
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
    logger.info(f"'{len(slices)}' Slices were retrieved")

    bi_model_by_docid = retrieve_models(docids, db_session, MLModelsType.BI_CLASSIFIER)
    logger.info(
        f"'{len({x.get('model_id') for x in bi_model_by_docid.values()})}' distinct bi-classifier models were retrieved",
    )

    n_model_by_docid = retrieve_models(docids, db_session, MLModelsType.N_CLASSIFIER)
    logger.info(
        f"'{len({x.get('model_id') for x in n_model_by_docid.values()})}' distinct n-classifier models were retrieved"
    )

    # Classify slices
    non_sdg_docs_ids: set[UUID] = set()
    sdg_docs_ids: set[UUID] = set()
    specific_sdgs: List[Sdg] = []
    logger.info("Starting bi-classification")
    key_external_sdg = "external_sdg"
    slices_per_docs: list[DocumentSlice] = sorted(slices, key=lambda x: x.document_id)  # type: ignore

    # Group slices by document id
    key_doc_id: UUID
    for key_doc_id, group_doc_slices in groupby(
        slices_per_docs, lambda x: x.document_id
    ):
        doc_slices: List[DocumentSlice] = list(group_doc_slices)  # type: ignore

        bi_model_name = bi_model_by_docid.get(key_doc_id, dict()).get("model_name")
        bi_model_id: UUID = bi_model_by_docid.get(key_doc_id, dict()).get("model_id")
        if not bi_model_name and not isinstance(bi_model_name, str):
            logger.warning("No bi-classifier model found for document %s", key_doc_id)
            continue
        if not bi_model_id and not isinstance(bi_model_id, UUID):
            logger.warning(
                "No bi-classifier model id found for document %s", key_doc_id
            )
            continue
        logger.info(
            "Bi-classifying document %s with model %s", key_doc_id, bi_model_name
        )

        n_model_name: str = n_model_by_docid.get(key_doc_id, dict()).get("model_name")
        n_model_id: UUID = n_model_by_docid.get(key_doc_id, dict()).get("model_id")
        if not n_model_name:
            logger.warning("No n-classifier model found for document %s", key_doc_id)
            continue
        if not n_model_id:
            logger.warning("No n-classifier model id found for document %s", key_doc_id)
            continue
        logger.info("n-classifying document %s with model %s", key_doc_id, n_model_name)

        for s in doc_slices:
            if not isinstance(s.document.details, dict):
                logger.error(f"Details is not a dict in this slice :{s.id}")
                raise ValueError(f"Details is not a dict in this slice :{s.id}")

            externaly_classified_flag = (
                key_external_sdg in s.document.details
                and s.document.details[key_external_sdg]
            )
            if bi_classify_slice(slice_=s, classifier_model_name=bi_model_name):
                specific_sdg = n_classify_slice(
                    _slice=s,
                    classifier_model_name=n_model_name,
                    forced_sdg=(
                        s.document.details[key_external_sdg]
                        if externaly_classified_flag
                        else None
                    ),
                    bi_classifier_id=bi_model_id,
                    n_classifier_id=n_model_id,
                )
                if not specific_sdg:
                    continue
                specific_sdgs.append(specific_sdg)
                sdg_docs_ids.add(key_doc_id)

    non_sdg_docs_ids = {
        k.document_id for k in slices_per_docs if k.document_id not in sdg_docs_ids
    }

    # Delete old slices
    logger.info("Delete old SDGs")
    db_session.query(Sdg).filter(
        Sdg.slice_id.in_([s.slice_id for s in specific_sdgs])
    ).delete()
    db_session.commit()

    # Update SDGs
    logger.info("Updating SDGs")
    db_session.add_all(specific_sdgs)

    # Create process states
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
