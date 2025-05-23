import logging
import os
import uuid
from typing import List

from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import (
    Keyword,
    ProcessState,
    WeLearnDocument,
    WeLearnDocumentKeyword,
)
from welearn_datastack.data.enumerations import MLModelsType, Step
from welearn_datastack.modules.keywords_extractor import extract_keywords
from welearn_datastack.modules.retrieve_data_from_database import retrieve_models
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path
from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError("Log level is not recognized : '%s'" % log_level)

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("KeywordsExtractor starting...")
    input_artifact = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url json name: %s", input_artifact)

    input_directory, _ = setup_local_path()

    docids = retrieve_ids_from_csv(
        input_artifact=input_artifact, input_directory=input_directory
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve WeLearnDocument from database
    logger.info("Retrieve WeLearnDocument from database")
    welearn_documents: List = (
        db_session.query(WeLearnDocument).filter(WeLearnDocument.id.in_(docids)).all()
    )
    logger.info("'%s' WeLearnDocuments were retrieved", len(welearn_documents))

    # Check if welearn_documents is empty
    if not welearn_documents:
        logger.warning("No WeLearnDocuments found for the provided IDs.")
        return

    # Retrieve EmbeddingModel from database
    logger.info("Retrieve EmbeddingModel from database")
    emb_model_by_docid = retrieve_models(docids, db_session, MLModelsType.EMBEDDING)

    # Extract keywords from descriptions
    logger.info("Starting keywords extraction")
    for wld in welearn_documents:
        # Delete previous relations
        db_session.query(WeLearnDocumentKeyword).filter(
            WeLearnDocumentKeyword.welearn_document_id == wld.id
        ).delete()
        embedding_model_name_from_db = emb_model_by_docid.get(wld.id)
        if not embedding_model_name_from_db:
            logger.warning(
                "No embedding model found for document ID '%s'. Skipping keywords extraction.",
                wld.id,
            )
            continue
        kwds = extract_keywords(
            wld, embedding_model_name_from_db=embedding_model_name_from_db
        )
        for kw in kwds:
            existing_keyword = db_session.query(Keyword).filter_by(keyword=kw).first()
            if not existing_keyword:
                kw_id = uuid.uuid4()
                db_session.add(
                    Keyword(
                        id=kw_id,
                        keyword=kw,
                    )
                )
            else:
                kw_id = existing_keyword.id

            db_session.add(
                WeLearnDocumentKeyword(
                    id=uuid.uuid4(),
                    welearn_document_id=wld.id,
                    keyword_id=kw_id,
                )
            )

    # Create process states
    logger.info("Creating process states")
    for doc_id in docids:
        db_session.add(
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_id,
                title=Step.DOCUMENT_KEYWORDS_EXTRACTED.value,
            )
        )
    db_session.commit()
    db_session.close()


if __name__ == "__main__":
    load_dotenv_local()
    main()
