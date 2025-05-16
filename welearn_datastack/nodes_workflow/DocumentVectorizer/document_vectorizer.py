import logging
import os
import uuid

from sqlalchemy.orm import Session
from torch.nn.functional import embedding

from welearn_datastack.data.db_models import (
    DocumentSlice,
    ProcessState,
    WeLearnDocument,
)
from welearn_datastack.data.enumerations import Step
from welearn_datastack.exceptions import NoModelFoundError
from welearn_datastack.modules.embedding_model_helpers import (
    create_content_slices,
    get_document_embedding_model_name_from_corpus_name,
)
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError(f"Log level is not recognized : '{log_level}'")

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("DocumentCollectorHub starting...")
    input_artifact = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url json name: %s", input_artifact)

    input_directory, local_artifact_output = setup_local_path()

    docids = retrieve_ids_from_csv(
        input_artifact=input_artifact, input_directory=input_directory
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve WeLearnDocument from database
    logger.info("Retrieve WeLearnDocument from database")
    welearn_documents: list[WeLearnDocument] = (  # type: ignore
        db_session.query(WeLearnDocument).filter(WeLearnDocument.id.in_(docids)).all()
    )

    logger.info("'%s' WeLearnDocuments were retrieved", len(welearn_documents))

    if not welearn_documents:
        logger.info("No WeLearnDocuments were retrieved")
        return

    if len(docids) != len(welearn_documents):
        logger.warning(
            "'%s' IDs URLs were not found in the database",
            len(docids) - len(welearn_documents),
        )

    # Create content slices
    docids_processed = 0
    docsids_not_processed = 0
    for i, document in enumerate(welearn_documents):
        logger.info("Processing document %s/%s", i, len(welearn_documents))
        try:
            embedding_model_from_db = (
                get_document_embedding_model_name_from_corpus_name(
                    session=db_session, corpus_id=document.corpus_id
                )
            )
            slices = create_content_slices(document, embedding_model_from_db=embedding_model_from_db)  # type: ignore
            logger.info("Delete old slices")
            db_session.query(DocumentSlice).filter(
                DocumentSlice.document_id == document.id
            ).delete()
            db_session.commit()
            logger.info("Insert new slices")
            db_session.add_all(slices)
            logger.info("Insert new state")
            db_session.add(
                ProcessState(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    title=Step.DOCUMENT_VECTORIZED.value,
                )
            )
            db_session.commit()
            logger.info("'%s' slices were created", len(slices))
            docids_processed += 1
        except NoModelFoundError:
            logger.error("No model found for document %s", document.id)
            db_session.add(
                ProcessState(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    title=Step.KEPT_FOR_TRACE.value,
                )
            )
            db_session.commit()
            docsids_not_processed += 1
            continue

    logger.info("'%s' documents were processed", docids_processed)
    logger.info("'%s' documents were not processed", docsids_not_processed)

    db_session.close()
    logger.info("DocumentVectorizer finished")


if __name__ == "__main__":
    main()
