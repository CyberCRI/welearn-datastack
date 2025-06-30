import logging
from collections import defaultdict
from functools import cache
from typing import Collection, Dict, List, Set, Type
from uuid import UUID

import numpy
from qdrant_client import QdrantClient
from qdrant_client.grpc import UpdateResult
from qdrant_client.http.models import models

from welearn_datastack.constants import QDRANT_MULTI_LINGUAL_CODE
from welearn_datastack.data.db_models import DocumentSlice
from welearn_datastack.exceptions import (
    ErrorWhileDeletingChunks,
    NoPreviousCollectionError,
    VersionNumberError,
)

logger = logging.getLogger(__name__)


def classify_documents_per_collection(
    qdrant_connector: QdrantClient, slices: Collection[Type[DocumentSlice]]
) -> Dict[str, Set[UUID]]:
    """
    Classify documents per collection in Qdrant.

    .. warning::
    It's return the last version of the collection

    :param qdrant_connector: Qdrant client
    :param slices: List of slices
    :return: Dictionary with the collection names as keys and the document ids as values
    """
    tmp_collections_names_in_qdrant = qdrant_connector.get_collections().collections
    collections_names_in_qdrant = [c.name for c in tmp_collections_names_in_qdrant]
    model_name_collection_name = {
        x.split("_")[3]: x for x in collections_names_in_qdrant
    }

    ret: Dict[str, Set[UUID]] = defaultdict(set)
    for dslice in slices:
        model_name = dslice.embedding_model.title
        try:
            collection_name = model_name_collection_name[model_name]
            ret[collection_name].add(dslice.document_id)  # type: ignore
        except KeyError:
            logger.warning(
                "No collection found for model %s, document %s",
                model_name,
                dslice.document_id,
            )
            continue

    return ret


def delete_points_related_to_document(
    collection_name: str,
    qdrant_connector: QdrantClient,
    documents_ids: List[UUID],
    qdrant_wait: bool,
) -> UpdateResult | None:
    """
    Deletes all points related to a document in a collection
    :param qdrant_wait: Flag to wait for the insertion to be done
    :param collection_name: Name of the collection
    :param qdrant_connector: Qdrant connector
    :param documents_ids: Urls of the documents to delete
    """
    logger.info("Deletion started")
    logger.debug(f"Deleting points related to {documents_ids} in {collection_name}")
    op_res = None

    try:
        op_res = qdrant_connector.delete(
            collection_name=f"{collection_name}",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchAny(
                                any=[str(doc_id) for doc_id in documents_ids]
                            ),
                        ),
                    ],
                )
            ),
            wait=qdrant_wait,
        )
    except Exception as e:
        raise ErrorWhileDeletingChunks(f"Error while deleting chunk: {e}")

    if op_res:
        logger.debug(f"Deleted points related to {documents_ids} in {collection_name}")
    else:
        raise ErrorWhileDeletingChunks(
            f"Error while deleting chunk, no answer from server"
        )
    logger.info("Deletion finished")
    return op_res


def convert_slice_in_qdrant_point(
    slice_to_convert: Type[DocumentSlice], document_sdgs: List[int], slice_sdg: int
) -> models.PointStruct:
    vector = numpy.frombuffer(
        bytes(slice_to_convert.embedding), dtype=numpy.float32
    ).tolist()
    ret = models.PointStruct(
        id=str(slice_to_convert.id),
        vector=vector,
        payload={
            "document_title": slice_to_convert.document.title,
            "document_id": str(slice_to_convert.document_id),
            "document_url": slice_to_convert.document.url,
            "document_lang": slice_to_convert.document.lang,
            "slice_content": slice_to_convert.body,
            "document_corpus": slice_to_convert.document.corpus.source_name,
            "document_desc": slice_to_convert.document.description,
            "document_details": slice_to_convert.document.details,
            "document_scrape_date": slice_to_convert.document.created_at,
            "document_sdg": document_sdgs,
            "slice_sdg": slice_sdg,
        },
    )

    return ret
