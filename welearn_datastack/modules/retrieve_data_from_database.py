import logging
from datetime import datetime, timedelta
from typing import Collection, Dict, List, Type
from uuid import UUID

from sqlalchemy import Column, and_, desc, func
from sqlalchemy.orm import Query

from welearn_datastack.data.db_models import (
    BiClassifierModel,
    Corpus,
    CorpusBiClassifierModel,
    CorpusNClassifierModel,
    DocumentSlice,
    NClassifierModel,
    ProcessState,
    Sdg,
    WeLearnDocument,
)
from welearn_datastack.data.enumerations import (
    MLModelsType,
    Step,
    URLRetrievalType,
    WeighedScope,
)
from welearn_datastack.types import QuerySizeLimitDocument, QuerySizeLimitSlice

logger = logging.getLogger(__name__)


def _generate_process_state_sub_query(session):
    """
    Generate subquery to retrieve the last process state for each document
    :param session: DB session
    :return: Subquery
    """
    subquery = (
        session.query(
            ProcessState.document_id,
            func.max(ProcessState.operation_order).label("operation_order"),
        )
        .group_by(ProcessState.document_id)
        .subquery()
    )
    return subquery


def _generate_query_size_limit(
    session, generated_query_goal: WeighedScope, corpus_name="*"
) -> Query:
    """
    Generate query to retrieve data from DB with size limit
    :param session:
    :param corpus_name:
    :return:
    """
    subquery = _generate_process_state_sub_query(session)

    if generated_query_goal == WeighedScope.DOCUMENT:
        query = (
            session.query(
                ProcessState.document_id,
                ProcessState.title,
                func.octet_length(WeLearnDocument.full_content),
            )
            .join(
                subquery,
                (ProcessState.document_id == subquery.c.document_id)
                & (ProcessState.operation_order == subquery.c.operation_order),
            )
            .join(WeLearnDocument, ProcessState.document_id == WeLearnDocument.id)
        )
    elif generated_query_goal == WeighedScope.SLICE:
        query = (
            session.query(
                ProcessState.document_id,
                ProcessState.title,
                func.octet_length(DocumentSlice.body),
                func.octet_length(DocumentSlice.embedding),
            )
            .join(
                subquery,
                (ProcessState.document_id == subquery.c.document_id)
                & (ProcessState.operation_order == subquery.c.operation_order),
            )
            .join(DocumentSlice, ProcessState.document_id == DocumentSlice.document_id)
            .order_by(ProcessState.document_id, desc(ProcessState.operation_order))
        )
    else:
        raise ValueError("Generated query goal not recognized")

    # Filter on corpus
    if corpus_name != "*":
        query = query.join(Corpus).filter(Corpus.source_name == corpus_name)  # type: ignore

    return query


def retrieve_urls_ids(
    session, mode: URLRetrievalType, corpus_name="*", qty_max=None
) -> List[str]:
    """
    Get URL from URLDataStore
    :param mode: Mode of URL retrieval
    :param session: DB session
    :param qty_max: Max number of URL to retrieve
    :param corpus_name: Name of corpus to retrieve
    :return: List of url ids
    """

    query = _generate_query_size_limit(
        session=session,
        generated_query_goal=WeighedScope.DOCUMENT,
        corpus_name=corpus_name,
    )

    query = query.order_by(desc(ProcessState.operation_order))

    # Determine filter
    match mode:
        case URLRetrievalType.NEW_MODE:
            logger.info("Retrieve new URLs")

            # The last process state is url_retrieved
            query = query.filter(
                ProcessState.title == "url_retrieved",
            )
        case URLRetrievalType.UPDATE_MODE:
            logger.info("Retrieve updated URLs")
            two_weeks_ago = datetime.now() - timedelta(hours=2)

            # Having at least 1 url_retrieved and other process flag
            query = query.filter(
                and_(
                    ProcessState.title == "document_in_qdrant",
                    ProcessState.created_at < two_weeks_ago,
                )
            )
        case _:
            raise ValueError("Mode not recognized")

    # Retrieve data from DB
    db_data: List = query.limit(qty_max).all()
    session.close()

    logger.info("Found %s results", len(db_data))

    return [x[0] for x in db_data]


def retrieve_documents_ids_according_process_title(
    session,
    process_titles: List[Step],
    weighed_scope: WeighedScope,
    corpus_name="*",
    qty_max=100,
    size_total_max: int | None = None,
) -> List[str]:
    """
    Get Document IDs from DB according to the last process title
    :param weighed_scope: Weighed scope of the query (document or slice)
    :param size_total_max: Max size of the batch, in bytes
    :param process_titles: List of process titles to retrieve
    :param session: DB session
    :param qty_max: Max number of URL to retrieve
    :param corpus_name: Name of corpus to retrieve
    :return: List of url ids
    """
    titles = [step.value for step in process_titles]

    query = _generate_query_size_limit(
        session=session,
        corpus_name=corpus_name,
        generated_query_goal=weighed_scope,
    )

    query = query.order_by(desc(ProcessState.operation_order))

    # Retrieve data from DB If the weighed scope is document, the query will return a list of tuples with the
    # document id, the process title and the size of the document.
    # If the weighed scope is slice, the query will
    # return a list of tuples with the document id, the process title, the size of the body and the size of the
    # embedding.
    db_data: List[QuerySizeLimitDocument] | List[QuerySizeLimitSlice] = (
        query.filter(ProcessState.title.in_(titles)).limit(qty_max).all()
    )
    session.close()

    # Filter on total size
    if size_total_max is not None:
        logger.info("Filtering on total size")

        if weighed_scope == WeighedScope.DOCUMENT:
            logger.info(
                "Filtering on document size, every values are in bytes an concern the full_content field"
            )
            total_size = sum([x[2] for x in db_data])  # type: ignore
        elif weighed_scope == WeighedScope.SLICE:
            # Sum of body and embedding
            logger.info(
                "Filtering on slice size, evey values are in bytes an concern the body and embedding fields"
            )
            total_size = sum([x[2] + x[3] for x in db_data])  # type: ignore
        else:
            raise ValueError("Weighed scope not recognized")

        # If total size is bigger than the limit, filter
        if total_size > size_total_max:
            logger.info("Total size of the batch is too big, filtering")
            size_accumulated = 0
            db_data_filtered = []
            for doc in db_data:
                if weighed_scope == WeighedScope.DOCUMENT:
                    size = doc[2] or 0
                elif weighed_scope == WeighedScope.SLICE:
                    # Sum of body and embedding
                    size = (doc[2] or 0) + (doc[3] or 0)  # type: ignore
                else:
                    raise ValueError("Weighed scope not recognized")

                if size_accumulated + size > size_total_max:
                    break

                size_accumulated += size
                db_data_filtered.append(doc)
            logger.info(
                "Filtered batch size: %s", sum([x[2] for x in db_data_filtered])
            )
            logger.info("Batch size: %s Bytes", size_accumulated)
            db_data = db_data_filtered  # type: ignore
    else:
        logger.info("No size limit set")

    logger.info("Found %s results", len(db_data))

    return [str(x[0]) for x in db_data]


def retrieve_random_documents_ids_according_process_title(
    session,
    process_titles: List[Step],
    corpus_name="*",
    qty_max=100,
) -> List[str]:
    """
    Get random Document IDs from DB according to the last process title
    :param process_titles: List of process titles to retrieve
    :param session: DB session
    :param qty_max: Max number of URL to retrieve
    :param corpus_name: Name of corpus to retrieve
    :return: List of url ids
    """
    titles = [step.value for step in process_titles]

    query = _generate_query_size_limit(
        session=session,
        corpus_name=corpus_name,
        generated_query_goal=WeighedScope.DOCUMENT,
    )

    # Retrieve random data from DB
    db_data: List[QuerySizeLimitDocument] | List[QuerySizeLimitSlice] = (
        query.filter(ProcessState.title.in_(titles))
        .order_by(func.random())
        .limit(qty_max)
        .all()
    )

    logger.info("Found %s results", len(db_data))

    return [str(x[0]) for x in db_data]


def retrieve_models(
    documents_ids: List[UUID], db_session, ml_type: MLModelsType
) -> List[BiClassifierModel] | List[NClassifierModel]:
    """
    Retrieve models from DB
    :param ml_type: Type of ML model to retrieve
    :param documents_ids: List of document ids
    :param db_session: DB session
    :return: List of DocumentSlice
    """
    model_table: type[BiClassifierModel] | type[NClassifierModel]
    join_table: type[CorpusBiClassifierModel] | type[CorpusNClassifierModel]
    if ml_type == MLModelsType.BI_CLASSIFIER:
        model_table = BiClassifierModel
        join_table = CorpusBiClassifierModel
        relation_name = "bi_classifier_model_id"
    elif ml_type == MLModelsType.N_CLASSIFIER:
        model_table = NClassifierModel
        join_table = CorpusNClassifierModel
        relation_name = "n_classifier_model_id"
    else:
        raise ValueError("ML type not recognized")

    query = (
        db_session.query(model_table.title, model_table.lang)
        .join(
            join_table,
            getattr(join_table, relation_name) == model_table.id,
        )
        .join(
            WeLearnDocument,
            WeLearnDocument.corpus_id == join_table.corpus_id,
        )
        .join(
            DocumentSlice,
            DocumentSlice.document_id == WeLearnDocument.id,
        )
        .filter(
            and_(
                DocumentSlice.document_id.in_(documents_ids),
                model_table.lang == WeLearnDocument.lang,
            )
        )
        .group_by(model_table.title, model_table.lang)
    )

    models = query.all()
    return models


def check_process_state_for_documents(
    db_session, documents_ids: List[UUID], steps: List[Step]
) -> List[UUID]:
    """
    Check the last process state for each document and return the documents with the last step in steps

    :param db_session: Database session
    :param documents_ids: Documents IDs to check the last step
    :param steps: List of steps to check
    :return: List of documents IDs with the last step in steps
    """
    steps_in_str = [step.value for step in steps]

    subquery = _generate_process_state_sub_query(db_session)

    # Return docs ids with the last step in steps
    query = (
        db_session.query(ProcessState.document_id)
        .join(
            subquery,
            (ProcessState.document_id == subquery.c.document_id)
            & (ProcessState.operation_order == subquery.c.operation_order),
        )
        .filter(
            ProcessState.title.in_(steps_in_str),
            ProcessState.document_id.in_(documents_ids),
        )
    )

    docs_ids = [x[0] for x in query.all()]
    return docs_ids


def retrieve_slices_sdgs(
    db_session, slices: Collection[Type[DocumentSlice]]
) -> Dict[UUID | Column["UUID"], int]:
    """
    Retrieve slices sdgs from a list of slices

    :param db_session: Database session
    :param slices: List of slices
    :return: Dictionary with slice id as key and sdg number as value
    """
    slices_sdgs = (
        db_session.query(Sdg.slice_id, Sdg.sdg_number)
        .filter(Sdg.slice_id.in_([s.id for s in slices]))
        .all()
    )

    if len(slices_sdgs) > len(slices):
        raise ValueError("There is too much SDGs for the slices")

    logger.info(
        "'%s' Slices SDGs were retrieved on '%s' slices", len(slices_sdgs), len(slices)
    )

    return {s[0]: s[1] for s in slices_sdgs}
