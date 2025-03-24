import csv
import logging
import uuid
from pathlib import Path
from typing import List
from uuid import UUID

logger = logging.getLogger(__name__)


def retrieve_ids_from_csv(input_artifact: str, input_directory: Path) -> List[UUID]:
    """
    Retrieve IDs from csv file and return them
    :param input_artifact: Path to the input file
    :param input_directory: Path to the local artifacts folder
    :return:
    """
    # retrieve url data from files
    logger.info("Retrieve URLs from file")
    # Input IDs
    with (input_directory / input_artifact).open("r") as artifact_file_input:
        spamreader = csv.reader(artifact_file_input, delimiter=",", quotechar='"')
        ids_urls: List[UUID] = [uuid.UUID(row[0]) for row in spamreader]
        logger.info("'%s' IDs URLs were retrieved", len(ids_urls))
    return ids_urls
