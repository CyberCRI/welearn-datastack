import logging
from functools import cache
from typing import Collection, Dict, List, Set, Type
from uuid import UUID

import numpy
from qdrant_client import QdrantClient
from qdrant_client.grpc import UpdateResult
from qdrant_client.http.models import models

from welearn_datastack.data.db_models import DocumentSlice
from welearn_datastack.exceptions import (
    ErrorWhileDeletingChunks,
    NoPreviousCollectionError,
    VersionNumberError,
)

logger = logging.getLogger(__name__)


def extract_version_number(collection_name: str) -> int:
    """
    Extracts the version number from a collection name
    :param collection_name: Name of the collection
    :return: Version number
    """
    splitted_infos = collection_name.split("_")
    version = splitted_infos[-1]
    try:
        version_number = int(version.replace("v", ""))
    except ValueError:
        raise VersionNumberError(
            f"Invalid version number, must be an integer: {version}"
        )
    return version_number


@cache
def get_last_collection_version(
    collection_name_first_part: str, qdrant_connector: QdrantClient
) -> int:
    """
    Returns the last version number of a collection in Qdrant.
    :param collection_name_first_part: Collection name apart the version number
    -> "collection_{corpus_name.lower()}_{lang_code.lower()}_{embedding_model_name.lower()}"
    :param qdrant_connector: Qdrant client
    :return: Higher number of version in db
    """
    db_collections_names = qdrant_connector.get_collections().collections
    filtered = [
        c.name
        for c in db_collections_names
        if c.name.startswith(collection_name_first_part)
    ]

    if not filtered:
        # Case there is no old collection
        logger.exception(
            "No previous collection found for : %s", collection_name_first_part
        )
        raise NoPreviousCollectionError("No previous collection found")

    versions: List[int] = [extract_version_number(c) for c in filtered]

    return max(versions)


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

    ret: Dict[str, Set[UUID]] = {}
    for dslice in slices:
        corpus = dslice.document.corpus.source_name.lower()
        lang = dslice.document.lang
        model = dslice.embedding_model_name
        first_part = f"collection_{corpus}_{lang}_{model.lower()}"

        version_number = get_last_collection_version(first_part, qdrant_connector)
        collection_name = f"{first_part}_v{version_number}"
        if collection_name not in collections_names_in_qdrant:
            logger.error(
                "Collection %s not found in Qdrant, slice %s ignored",
                collection_name,
                dslice.id,
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
    slice_to_convert: Type[DocumentSlice],
    document_sdgs: List[int],
    slice_sdg: list[int],
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
