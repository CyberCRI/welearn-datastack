import json
import os
import random
from functools import cached_property
from typing import List, Tuple

import numpy
from locust import HttpUser, tag, task  # type: ignore
from qdrant_client import QdrantClient
from qdrant_client.http.models import CollectionDescription, CollectionsResponse

from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local


class CollectionInformation:
    def __init__(self, name: str, vector_size: int):
        self.name: str = name
        self.vector_size: int = vector_size

    @cached_property
    def mock_vector(self):
        return numpy.random.rand(self.vector_size).tolist()


class User(HttpUser):
    def on_start(self):
        load_dotenv_local()

        qdrant_timeout: int = int(os.getenv("QDRANT_TIMEOUT", "60"))
        qdrant_grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
        qdrant_http_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
        qdrant_url: str = os.getenv("QDRANT_URL", "localhost")
        qdrant_prefers_grpc: bool = (
            os.getenv("QDRANT_PREFERS_GRPC", "False").lower() == "true"
        )

        qdrant_client = QdrantClient(
            url=qdrant_url,
            port=qdrant_http_port,
            grpc_port=qdrant_grpc_port,
            prefer_grpc=qdrant_prefers_grpc,
            timeout=qdrant_timeout,
            https=True,
        )
        collections: CollectionsResponse = qdrant_client.get_collections()
        collections_information: List[CollectionInformation] = []
        for collection in collections.collections:
            infos = qdrant_client.get_collection(collection_name=collection.name)
            collections_information.append(
                CollectionInformation(
                    name=collection.name, vector_size=infos.config.params.vectors.size
                )
            )

        self.collections = collections_information

    @tag("qdrant", "chat")
    @task
    def search_unique_collection(self):
        requested_collection: CollectionInformation = random.choice(self.collections)

        json_post = {"query": requested_collection.mock_vector, "limit": 100}

        with self.client.post(
            url=f"/collections/{requested_collection.name}/points/query",
            json=json_post,
            catch_response=True,
        ) as response:
            if response.json()["status"] == "ok" and len(response.json()["result"]) > 0:
                response.success()
            else:
                response.failure(
                    exc=f"Staus : {response.json()["status"]} and result len: {len(response.json()["result"])}"
                )

    @tag("qdrant", "search")
    @task
    def group_unique_collection(self):
        requested_collection: CollectionDescription = random.choice(self.collections)
        json_post = {
            "query": requested_collection.mock_vector,
            "group_by": "document_id",
            "limit": 100,
            "group_size": 1,
        }
        with self.client.post(
            url=f"/collections/{requested_collection.name}/points/query/groups",
            json=json_post,
            catch_response=True,
        ) as response:
            if response.json()["status"] == "ok" and len(response.json()["result"]) > 0:
                response.success()
            else:
                response.failure(
                    exc=f"Staus : {response.json()["status"]} and result len: {len(response.json()["result"])}"
                )
