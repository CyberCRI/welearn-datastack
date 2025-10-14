import csv
import logging
import os
import uuid
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from welearn_database.data.enumeration import Step
from welearn_database.data.models import ErrorRetrieval, ProcessState, WeLearnDocument

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import PluginNotFoundError
from welearn_datastack.modules import collector_selector
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
        doc_db_urls_dict: Dict[str, WeLearnDocument] = {
            doc.url: doc for doc in batch_docs[corpus_name]  # type: ignore
        }
        # Get data
        corpus_collector = corpus_plugin[corpus_name]
        scraped_docs, error_docs_tmp = corpus_collector.run(
            urls=[d.url for d in batch_docs[corpus_name]]  # type: ignore
        )

        handle_scraped_docs(
            scraped_docs=scraped_docs,
            ret_documents=ret_documents,
            states=states,
            doc_db_urls_dict=doc_db_urls_dict,
        )

        logger.info(
            "'%s' documents were on error for %s", len(error_docs_tmp), corpus_name
        )

        # Error documents
        handle_scraping_errors(
            corpus_name,
            doc_db_urls_dict,
            error_docs,
            error_docs_tmp,
            states,
        )

        logger.info(
            "'%s' documents were retrieved for %s", len(scraped_docs), corpus_name
        )
    return ret_documents, error_docs, states


def handle_scraping_errors(
    corpus_name: str,
    doc_db_urls_dict: Dict[str, WeLearnDocument],
    errors: List[ErrorRetrieval],
    error_docs_tmp: List[str],
    states: List[ProcessState],
) -> None:
    """
    Handle scraping errors and update the error documents
    :param corpus_name: Corpus name related to the error
    :param doc_db_urls_dict: Dictionary where the key is the document url and the value is the document
    :param errors: List of error documents
    :param error_docs_tmp: List of error url
    :param states: List of process states to insert
    :return:
    """
    for error_url in error_docs_tmp:
        doc_from_db = doc_db_urls_dict.get(error_url)
        if doc_from_db is None:
            logger.warning(
                "Scraped document with url '%s' was not found in the input documents",
                error_url,
            )
            continue
        errors.append(
            ErrorRetrieval(
                id=uuid.uuid4(),
                document_id=doc_from_db.id,
                error_info=f"Error while retrieving document {error_url} for {corpus_name}",
            )
        )
        states.append(
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_from_db.id,
                title=Step.DOCUMENT_IS_IRRETRIEVABLE.value,
            )
        )


def handle_scraped_docs(
    scraped_docs: List[ScrapedWeLearnDocument],
    doc_db_urls_dict: Dict[str, WeLearnDocument],
    ret_documents: List[WeLearnDocument],
    states: List[ProcessState],
) -> None:
    """
    Handle scraped documents and update the documents
    :param scraped_docs: List of scraped documents to handle
    :param doc_db_urls_dict: Dictionnary where the key is the document url and the value is the document
    :param ret_documents: List of documents to return
    :param states: List of process states to insert
    :return: None
    """

    for scraped_doc in scraped_docs:
        doc_from_db = doc_db_urls_dict.get(scraped_doc.document_url)
        if doc_from_db is None:
            logger.warning(
                "Scraped document with url '%s' was not found in the input documents",
                scraped_doc.document_url,
            )
            continue

        if doc_from_db.trace == scraped_doc.trace:
            logger.info("Document '%s' is already up to date", doc_from_db.id)

        # Document update
        doc_from_db.lang = scraped_doc.document_lang  # type: ignore
        doc_from_db.full_content = scraped_doc.document_content  # type: ignore
        doc_from_db.description = scraped_doc.document_desc  # type: ignore
        doc_from_db.details = scraped_doc.document_details  # type: ignore
        doc_from_db.trace = scraped_doc.trace  # type: ignore
        doc_from_db.title = scraped_doc.document_title  # type: ignore
        ret_documents.append(doc_from_db)

        # Process state creation
        states.append(
            ProcessState(
                id=uuid.uuid4(),
                document_id=doc_from_db.id,
                title=Step.DOCUMENT_SCRAPED.value,
            )
        )


if __name__ == "__main__":
    load_dotenv_local()
    main()
