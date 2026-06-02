import csv
import logging
import os
import uuid
from typing import Dict, List
from uuid import UUID

from sqlalchemy import exc
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from welearn_database.data.enumeration import Step
from welearn_database.data.models import ProcessState, WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.exceptions import PluginNotFoundError
from welearn_datastack.modules import collector_selector
from welearn_datastack.modules.computed_metadata import (
    compute_duration,
    compute_readability,
    identify_document_language,
    serialize_dataclass_instance,
)
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

    local_artifcat_input, _ = setup_local_path()

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
    all_documents = extract_data_from_urls(welearn_documents)

    # Filter
    correct_docs = [d for d in all_documents if not d.is_error]
    errors = [d for d in all_documents if d.is_error]
    logger.info("'%s' documents were correctly retrieved", len(correct_docs))
    logger.info("'%s' documents were in error during retrievement", len(errors))

    #  Data insertion
    insertion_error = _insert_documents(db_session, correct_docs)
    errors.extend([e for e in insertion_error if e not in errors])
    _insert_errors(db_session, errors)

    logger.info("Data insertion - Documents and errors were inserted in database")

    db_session.commit()
    db_session.close()
    logger.info("DocumentCollectorHub finished")


def _insert_documents(
    db_session, docs: list[WrapperRetrieveDocument]
) -> list[WrapperRetrieveDocument]:
    """
    Insert documents in database and their states
    :db_session: Database session
    :docs: Not in error documents to insert
    :return: List of documents in error during insertion
    """
    ret_errors: list[WrapperRetrieveDocument] = []
    duplicates_errors: list[WrapperRetrieveDocument] = []
    retrievement_errors: list[WrapperRetrieveDocument] = []

    for wrapper_retrieve_document in docs:
        if wrapper_retrieve_document.is_error:
            retrievement_errors.append(wrapper_retrieve_document)
            continue

        if not wrapper_retrieve_document.document.details:
            wrapper_retrieve_document.document.details = {}
        identify_document_language(wrapper_retrieve_document.document)
        compute_duration(wrapper_retrieve_document.document)
        compute_readability(wrapper_retrieve_document.document)
        serialize_dataclass_instance(wrapper_retrieve_document.document)
        flag_modified(wrapper_retrieve_document.document, "details")
        try:
            with db_session.begin_nested():
                db_session.add(wrapper_retrieve_document.document)
                db_session.add(
                    ProcessState(
                        document_id=wrapper_retrieve_document.document.id,
                        title=Step.DOCUMENT_SCRAPED.value,
                    )
                )
        except exc.IntegrityError as e:
            logger.warning(
                "This document %s is a duplication",
                wrapper_retrieve_document.document.id,
                exc_info=e,
            )
            wrapper_retrieve_document.error_info = str(e)
            duplicates_errors.append(wrapper_retrieve_document)
    logger.info("Data extraction - URLs and documents were retrieved")

    ret_errors.extend(duplicates_errors)
    ret_errors.extend(retrievement_errors)
    logger.info("There is %s documents in error after insertion", len(ret_errors))
    return ret_errors


def _insert_errors(db_session, errors: list[WrapperRetrieveDocument]) -> None:
    """
    Insert errors in database and insert the related state
    :db_session: database session
    :errors: list of errors
    """
    for wrapper_retrieve_document in errors:
        db_session.add(wrapper_retrieve_document.to_error_retrieval())
        db_session.add(
            ProcessState(
                document_id=wrapper_retrieve_document.document.id,
                title=Step.DOCUMENT_IS_IRRETRIEVABLE.value,
            )
        )
    logger.info("%s Errors were inserted in database", len(errors))


def extract_data_from_urls(
    welearn_documents: list[WeLearnDocument],
) -> list[WrapperRetrieveDocument]:
    """
    Extract data from URLs by using the correct plugin for this related source
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
    corpus_plugin = _select_appropriate_plugin(batch_docs)

    # Retrieve documents
    logger.info("Retrieve documents")
    # Iterate on each corpus
    ret_docs: list[WrapperRetrieveDocument] = []
    for corpus_name in batch_docs:
        # Get data
        corpus_collector = corpus_plugin[corpus_name]
        documents = corpus_collector.run(documents=batch_docs[corpus_name])  # type: ignore

        ret_docs.extend(documents)
        logger.info(
            f"'{len(documents)}/{len(welearn_documents)}' documents were processed"
        )
    return ret_docs


def _select_appropriate_plugin(batch_docs: dict[str, list]) -> dict[str, IPlugin]:
    logger.info("Select appropriate plugin")
    corpus_plugin: Dict[str, IPlugin] = {}
    error_corpus_name: List[str] = []
    for corpus_name in batch_docs:
        try:
            current_plugin = collector_selector.select_collector(corpus=corpus_name)
        except PluginNotFoundError as e:
            logger.exception(e)
            logger.warning("This corpus '%s  will be ignored", corpus_name)
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
    return corpus_plugin


if __name__ == "__main__":
    load_dotenv_local()
    main()
