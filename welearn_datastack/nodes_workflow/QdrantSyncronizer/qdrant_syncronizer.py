import logging
import os
import uuid
from collections import Counter
from itertools import batched
from typing import Dict, Generator, List, Sequence, Tuple, Type
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, UpdateStatus
from qdrant_client.qdrant_remote import QdrantRemote
from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import DocumentSlice, ProcessState
from welearn_datastack.data.enumerations import Step
from welearn_datastack.modules.qdrant_handler import (
    classify_documents_per_collection,
    convert_slice_in_qdrant_point,
    delete_points_related_to_document,
)
from welearn_datastack.modules.retrieve_data_from_database import (
    check_process_state_for_documents,
    retrieve_slices_sdgs,
)
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path

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
    logger.info("QdrantSyncronizer starting...")

    logger.info("Load environment variables")
    qdrant_timeout: int = int(os.getenv("QDRANT_TIMEOUT", "60"))
    qdrant_grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    qdrant_http_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_url: str = os.getenv("QDRANT_URL", "localhost")
    qdrant_prefers_grpc: bool = (
        os.getenv("QDRANT_PREFERS_GRPC", "False").lower() == "true"
    )
    qdrant_wait: bool = os.getenv("QDRANT_WAIT", "False").lower() == "true"
    qdrant_chunk_size = int(os.getenv("QDRANT_CHUNK_SIZE", 1000))
    input_artifact = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")

    logger.info("Environment variables loaded")
    logger.info("Input artifact url json name: %s", input_artifact)
    logger.info("Qdrant URL: %s", qdrant_url)
    logger.info("Qdrant GRPC Port: %s", qdrant_grpc_port)
    logger.info("Qdrant HTTP Port: %s", qdrant_http_port)
    logger.info("Qdrant Prefers GRPC: %s", qdrant_prefers_grpc)
    logger.info("Qdrant chunk Size: %s", qdrant_chunk_size)

    input_directory, local_artifcat_output = setup_local_path()

    docids = retrieve_ids_from_csv(
        input_artifact=input_artifact, input_directory=input_directory
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    qdrant_chunk: batched[UUID] = batched(iterable=docids, n=qdrant_chunk_size)

    qdrant_client = QdrantClient(
        url=qdrant_url,
        port=qdrant_http_port,
        grpc_port=qdrant_grpc_port,
        prefer_grpc=qdrant_prefers_grpc,
        timeout=qdrant_timeout,
        https=True,
    )

    if isinstance(qdrant_client._client, QdrantRemote):
        qdrant_host = qdrant_client._client._host
        qdrant_port = qdrant_client._client._port
        logger.info(f"Qdrant client connected to {qdrant_host}:{qdrant_port}")

    for i, chunk in enumerate(qdrant_chunk):
        logger.info("Processing chunk: #%s", i)
        slices: Sequence[Type[DocumentSlice]] = (
            db_session.query(DocumentSlice)  # type: ignore
            .filter(DocumentSlice.document_id.in_(chunk))
            .all()
        )
        logger.info("'%s' Slices were retrieved", len(slices))

        # Group slices by document id
        slices_per_doc: Dict[UUID, List[Type[DocumentSlice]]] = {}
        for s in slices:
            if s.document_id not in slices_per_doc:
                slices_per_doc[s.document_id] = []  # type: ignore
            slices_per_doc[s.document_id].append(s)  # type: ignore

        # Get collections names
        documents_per_collection = classify_documents_per_collection(
            qdrant_connector=qdrant_client, slices=slices
        )

        # Iterate on each collection
        for collection_name in documents_per_collection:
            logger.info(f"We working on collection : {collection_name}")
            # We need to delete all points related to the documents in the collection for avoiding duplicates
            del_res = delete_points_related_to_document(
                collection_name=collection_name,
                qdrant_connector=qdrant_client,
                documents_ids=list(documents_per_collection[collection_name]),
                qdrant_wait=qdrant_wait,
            )
            logger.info("deletion operation result : %s", del_res)

            if not del_res:
                logger.error(
                    "Deletion operation failed for collection %s", collection_name
                )
                continue

            ids_doc_need_to_insert = check_process_state_for_documents(
                db_session=db_session,
                documents_ids=list(documents_per_collection[collection_name]),
                steps=[Step.DOCUMENT_KEYWORDS_EXTRACTED],
            )

            logger.info("Documents to insert: %s", len(ids_doc_need_to_insert))

            if len(ids_doc_need_to_insert) > 0:
                # Generate points if needed
                points: List[PointStruct] = []
                for docid in ids_doc_need_to_insert:
                    document_slices = slices_per_doc[docid]
                    slices_sdgs = retrieve_slices_sdgs(db_session, document_slices)
                    all_document_sdgs = [
                        slices_sdgs[s.id]  # type: ignore
                        for s in document_slices
                        if s.id in slices_sdgs
                    ]
                    accurate_sdgs = [
                        sdg for sdg, _ in Counter(all_document_sdgs).most_common(2)
                    ]
                    for doc_slice in document_slices:
                        # Filter slices with no SDG
                        if doc_slice.id in slices_sdgs:
                            points.append(
                                convert_slice_in_qdrant_point(
                                    slice_to_convert=doc_slice,
                                    document_sdgs=accurate_sdgs,
                                    slice_sdg=slices_sdgs[doc_slice.id],  # type: ignore
                                )
                            )

                # Insert points
                logger.info("Inserting points")
                insert_res = qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=qdrant_wait,
                )

                logger.info("Insertion operation result : %s", insert_res)

                # Add new process state
                logger.info("Adding new process state")
                if insert_res.status in [
                    UpdateStatus.ACKNOWLEDGED,
                    UpdateStatus.COMPLETED,
                ]:
                    for docid in ids_doc_need_to_insert:
                        db_session.add(
                            ProcessState(
                                id=uuid.uuid4(),
                                document_id=docid,
                                title=Step.DOCUMENT_IN_QDRANT.value,
                            )
                        )
                    db_session.commit()
                else:
                    logger.error(
                        "Insertion operation failed for collection %s", collection_name
                    )

            if del_res.status in [UpdateStatus.ACKNOWLEDGED, UpdateStatus.COMPLETED]:
                for docid in documents_per_collection[collection_name]:
                    if docid not in ids_doc_need_to_insert:
                        db_session.add(
                            ProcessState(
                                id=uuid.uuid4(),
                                document_id=docid,
                                title=Step.KEPT_FOR_TRACE.value,
                            )
                        )
                db_session.commit()
            else:
                logger.error(
                    "Deletion operation failed for collection %s", collection_name
                )

    logger.info("Closing DB session")
    db_session.close()
    logger.info("QdrantSyncronizer finished")


if __name__ == "__main__":
    main()
