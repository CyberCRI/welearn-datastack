# Welearn Datastack

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
## Introduction
This repository contains the datastack for the Welearn project. 
The datastack is a collection of scripts and tools that are used to :
- Ingest data from various sources
- Vectorize these data into embeddings
- Classify it
- Store it into relational et vector database

## Architecture
### Scripts
There are several scripts in this repository. Each of them comes into play at a specific point in the pipeline :

| Name                 | Path                                                                          | Description                                                                                  |
|----------------------|-------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| UrlCollectors       | `welearn_datastack/nodes_workflow/URLCollectors/*.py`                         | Collects URLs                                                                                |
| DocumentCollectorHub | `welearn_datastack/nodes_workflow/DocumentHubCollector/document_collector.py` | Collects documents via API, scraping or local files                                          |
| DocumentVectorizer   | `welearn_datastack/nodes_workflow/DocumentVectorizer/document_vectorizer.py`  | Cuts documents into slice and converts each one into embeddings                              |
| DocumentClassifier   | `welearn_datastack/nodes_workflow/DocumentClassifier/document_classifier.py`  | Classify the slices according to whether or not they mention the SDGs, and if so which ones. |
| KeywordsExtractor    | `welearn_datastack/nodes_workflow/KeywordsExtractor/keywords_extractor.py`    | Extract keywords from descriptions                                                                                             |
| QdrantSyncronizer    | `welearn_datastack/nodes_workflow/QdrantSyncronizer/qdrant_syncronizer.py`    | Sync with qdrant                                                                                             |

### Database (pgsql)
Without giving all details, the most important things to understand about his db is: everything is managed by the document "ProcessState".
Each scripts take documents based on this information. 

### Qdrant
You need te precreate each collections you gonna need. Their form is :
`collection_<coprus_name>_<language>_<vectorizer_name>_<collection_version>`

## Setup
### Requirements
- Python 3.12
- One relationnal database (We use a [PostgreSQL](https://www.postgresql.org/) one)
- One [qdrant](https://qdrant.tech/) instance

### Setup Environment
Create a virtual environment and install the requirements
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then create a file .env
```bash
touch .env
```

And fill it with the following content
```bash
# Database
PG_HOST=<str>
PG_PORT=<int>
PG_USER=<str>
PG_PASSWORD=<str>
PG_DATABASE=<str>
PG_DRIVER=<str>
PG_SCHEMA=document_related,corpus_related,user_related

# Qdrant
QDRANT_URL=<str>
QDRANT_HTTP_PORT=<int>
QDRANT_GRPC_PORT=<int>
QDRANT_PREFERS_GRPC=<bool>
QDRANT_WAIT=<bool>
QDRANT_CHUNK_SIZE=<int>

# Data ingestion
PDF_SIZE_PAGE_LIMIT=<int>
PDF_SIZE_FILE_LIMIT=<int>
PICK_QTY_MAX=<int>
PARALLELISM_URL_MAX=<int>
PARALLELISM_THRESHOLD=<int>
ARTIFACT_ROOT=<str>

# ai
ST_DEVICE=<cpu or cuda>
MODELS_PATH_ROOT=<str>

# Management
PICK_CORPUS_NAME=<corpus_name or *>
RETRIEVAL_MODE=<NEW_MODE or UPDATE_MODE>
IS_LOCAL=<bool>

# Log
LOG_LEVEL=INFO
LOG_FORMAT=[%(asctime)s][%(name)s][%(levelname)s] - %(message)s
```

### Setup the PostgreSQL database
1. Create a new database
2. Run alembic to create the tables
```bash
alembic upgrade head
```

### Setup Qdrant
Assuming you want to ingest corpus "wikipedia" and "PLOS" in english and french for the first one and only in english for the second one.
You're using **all-minilm-l6-v2** vectorizer for english and **sentence-camembert-base** for the french.
You need to create the following collections in qdrant:
- collection_welearn_en_all-minilm-l6-v2_v0
- collection_welearn_fr_sentence-camembert-base_v0

And for retrieving data from specific corpus you must use the `document_corpus` in payload field as it's written in [qdrant documentation](https://qdrant.tech/documentation/guides/multiple-partitions/).

Command for [create collection](https://qdrant.tech/documentation/concepts/collections/#create-a-collection) :
```
PUT collections/{collection_name}
{
  "vectors": {
    "size": {vector size for your model},
    "distance": "Cosine",
  }
}
```
You can use curl or going on the qdrant dashboard for run this command.

### Run the scripts
#### Special case : URLCollector
This script is split in multiples ones and doesn't need a list of ids.
So if you want to run URLC for hal and plos you need to :
```bash
python -m welearn_datastack.nodes_workflow.URLCollectors.node_hal_collect
```

Adn as PLOS use atom flux for publishing URL we use it like that :
```bash
export ATOM_URL=https://journals.plos.org/plosbiology/feed/atom
export CORPUS_NAME=plos
python -m welearn_datastack.nodes_workflow.URLCollectors.node_atom_collect
```

#### General case
**In first** place you need to run the batch generator. Taking here the example of DocumentHubCollector :
```bash
python -m welearn_datastack.nodes_workflow.DocumentHubCollector.generate_to_collect_batch
```
This script gonna fill the folder you specify in the .env file (ARTIFACT_ROOT) with the ids of the documents you want to collect. You need to copy it into input_folder for the next step.
```bash
cp $ARTIFACT_ROOT/output/batch_urls/0_batch_ids.csv input/batch_ids.csv
```

**Then** you can run the collector :
```bash
python -m welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector
```

**These two steps are mandatory for each script.**
