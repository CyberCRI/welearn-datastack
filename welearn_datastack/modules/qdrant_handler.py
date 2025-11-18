import logging
from typing import Collection, Dict, List, Set, Type
from uuid import UUID

import numpy
from qdrant_client import QdrantClient
from qdrant_client.grpc import UpdateResult
from qdrant_client.http.models import models
from welearn_database.data.models import DocumentSlice

from welearn_datastack.exceptions import ErrorWhileDeletingChunks

logger = logging.getLogger(__name__)


def classify_documents_per_collection(
    qdrant_connector: QdrantClient, slices: Collection[Type[DocumentSlice]]
) -> Dict[str | None, Set[UUID]]:
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

    ret: Dict[str | None, Set[UUID]] = {None: set()}
    for dslice in slices:
        lang = dslice.document.lang
        try:
            model = dslice.embedding_model.title
        except AttributeError:
            logger.error(
                f"Slice {dslice.id} has no updated embedding model, document ({dslice.document_id}) put in error",
            )
            ret[None].add(dslice.document_id)  # type: ignore
            continue

        collection_name = None
        multilingual_collection = f"collection_welearn_mul_{model}"
        mono_collection = f"collection_welearn_{lang}_{model}"

        # Check multilingual or mono lingual
        if multilingual_collection in collections_names_in_qdrant:
            collection_name = multilingual_collection
        elif mono_collection in collections_names_in_qdrant:
            collection_name = mono_collection
        else:
            logger.error(
                f"Collection {collection_name} not found in Qdrant, slice {dslice.id} ignored",
            )
            continue

        if collection_name not in ret:
            ret[collection_name] = set()
        ret[collection_name].add(dslice.document_id)  # type: ignore

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
