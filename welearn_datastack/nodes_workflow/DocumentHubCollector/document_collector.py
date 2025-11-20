import csv
import logging
import os
import uuid
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from welearn_database.data.enumeration import Step
from welearn_database.data.models import ErrorRetrieval, ProcessState, WeLearnDocument

from welearn_datastack.exceptions import PluginNotFoundError
from welearn_datastack.modules import collector_selector
from welearn_datastack.modules.computed_metadata import (
    compute_duration,
    compute_readability,
    identify_document_language,
)
from welearn_datastack.modules.validation import validate_non_null_fields_document
from welearn_datastack.plugins.interface import IPlugin
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
    logger.info("DocumentCollectorHub starting...")
    input_artifact_id_url = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url csv name: %s", input_artifact_id_url)

    local_artifcat_input, local_artifcat_output = setup_local_path()

    # retrieve url data from files
    logger.info("Retrieve URLs from file")

    # Input IDs
    with (local_artifcat_input / input_artifact_id_url).open(
        "r"
    ) as artifact_file_input:
        spamreader = csv.reader(artifact_file_input, delimiter=",", quotechar='"')
        ids_urls: List[UUID] = [uuid.UUID(row[0]) for row in spamreader]
        logger.info("'%s' IDs URLs were retrieved", len(ids_urls))

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve WeLearnDocument from database
    logger.info("Retrieve WeLearnDocument from database")
    welearn_documents: List = (
        db_session.query(WeLearnDocument).filter(WeLearnDocument.id.in_(ids_urls)).all()
    )
    logger.info("'%s' WeLearnDocuments were retrieved", len(welearn_documents))

    if len(ids_urls) != len(welearn_documents):
        logger.warning(
            "'%s' IDs URLs were not found in the database",
            len(ids_urls) - len(welearn_documents),
        )

    if not welearn_documents:
        logger.info("No WeLearnDocuments were retrieved")
        return

    # Data extraction
    logger.info("Data extraction - Retrieve URLs and documents")
    batch_documents, errors, states = extract_data_from_urls(welearn_documents)
    logger.info("Data extraction - URLs and documents were retrieved")

    # Compute some metadata
    logger.info("Compute some metadata for retrieved documents")
    for doc in batch_documents:
        if not doc.details:
            doc.details = {}
        identify_document_language(doc)
        compute_duration(doc)
        compute_readability(doc)
        flag_modified(doc, "details")

    db_session.add_all(states)
    db_session.add_all(errors)
    db_session.add_all(batch_documents)
    db_session.commit()


def extract_data_from_urls(
    welearn_documents: List[WeLearnDocument],
) -> Tuple[List[WeLearnDocument], List[ErrorRetrieval], List[ProcessState]]:
    """
    Extract_data_from_urls
    :param welearn_documents: input docs
    :return: URLs and documents retrieved from DB and web
    """
    batch_docs: Dict[str, List] = {}
    nonexistent_corpus_docs: List[str] = []
    for doc in welearn_documents:
        try:
            if doc.corpus.source_name not in batch_docs:
                batch_docs[doc.corpus.source_name] = []
            batch_docs[doc.corpus.source_name].append(doc)
        except Exception as e:
            nonexistent_corpus_docs.append(doc.url)  # type: ignore
            human_identifiable_couple = str((doc.id, doc.url))
            logger.error(
                "%s : Error while processing document, it was ignored: %s",
                e,
                human_identifiable_couple,
            )

    # Select appropriate plugins
    logger.info("Select appropriate plugin")
    corpus_plugin: Dict[str, IPlugin] = {}
    error_corpus_name: List[str] = []
    for corpus_name in batch_docs:
        try:
            current_plugin = collector_selector.select_collector(corpus=corpus_name)
        except PluginNotFoundError as e:
            logger.exception(e)
            logger.warning("This corpus '%s" " will be ignored", corpus_name)
            error_corpus_name.append(corpus_name)
            continue
        corpus_plugin[corpus_name] = current_plugin
        logger.debug(
            "'%s' plugin selected for corpus '%s'",
            current_plugin.__class__.__name__,
            corpus_name,
        )
    for corpus_name in error_corpus_name:
        del batch_docs[corpus_name]

    # Retrieve documents
    logger.info("Retrieve documents")
    ret_documents: List[WeLearnDocument] = []
    error_docs: List[ErrorRetrieval] = []
    states: List[ProcessState] = []

    # Iterate on each corpus
    for corpus_name in batch_docs:
        # Get data
        corpus_collector = corpus_plugin[corpus_name]
        documents = corpus_collector.run(documents=batch_docs[corpus_name])  # type: ignore

        for wrapper_document in documents:
            is_none_valid = validate_non_null_fields_document(wrapper_document.document)
            if not is_none_valid and not wrapper_document.is_error:
                wrapper_document.http_error_code = 422
                wrapper_document.error_info = (
                    "Mandatory fields are missing after extraction"
                )

            state_title = (
                Step.DOCUMENT_SCRAPED.value
                if not wrapper_document.is_error
                else Step.DOCUMENT_IS_IRRETRIEVABLE.value
            )
            if not wrapper_document.is_error:
                ret_documents.append(wrapper_document.document)
            else:
                error_docs.append(wrapper_document.to_error_retrieval())
            states.append(
                ProcessState(
                    id=uuid.uuid4(),
                    document_id=wrapper_document.document.id,
                    title=state_title,
                )
            )
        logger.info(
            f"'{len(ret_documents)}/{len(welearn_documents)}' documents were retrieved for {corpus_name}"
        )
        logger.info(
            f"'{len(error_docs)}/{len(welearn_documents)}' errors were retrieved for {corpus_name}"
        )
    return ret_documents, error_docs, states


if __name__ == "__main__":
    load_dotenv_local()
    main()
