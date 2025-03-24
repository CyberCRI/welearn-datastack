import csv
import logging
import os
from itertools import batched
from pathlib import Path
from typing import Collection, List

from welearn_datastack.exceptions import NotBatchFoundError
from welearn_datastack.utils_.path_utils import setup_local_path

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError(f"Log level is not recognized : '{log_level}'")

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


class BatchGenerator:
    def __init__(
        self,
        parallelism_threshold: int = 100,
        parallelism_max: int = 15,
        batch_urls_directory: str = "batch_urls",
        output_batch_file_name: str = "batch_urls.csv",
        output_quantity_file: str = "quantity.txt",
    ):
        self.local_artifact_input, self.local_artifact_output = setup_local_path()

        self.output_batch_file = output_batch_file_name
        self.parallelism_threshold = parallelism_threshold
        self.parallelism_max = parallelism_max
        self.batch_urls_directory = batch_urls_directory
        self.batches: List[List[str]] = []
        self.output_quantity_file = output_quantity_file

    def create_ids_batch(self, documents_ids: Collection[str]) -> List[List[str]]:
        """
        Create a batch of documents ids
        :param documents_ids: List of documents ids
        :return: List of batches of documents ids
        """
        logger.info("Create batch of documents ids")
        ret: List[List[str]] = []

        batches = batched(documents_ids, self.parallelism_threshold)

        for i, batch in enumerate(batches):
            if i >= self.parallelism_max:
                logger.error(
                    "Max parallelism reached, %s ids will be processed in %s batches",
                    len(documents_ids) * self.parallelism_threshold,
                    len(documents_ids),
                )
                break
            else:
                ret.append(list(batch))

        self.batches = ret  # type: ignore
        return self.batches

    def write_batches_to_file(self):
        """
        :return:
        """
        if not self.batches:
            logger.exception("No batches to write")
            raise NotBatchFoundError("No batches to write")

        for i, batch in enumerate(self.batches):
            self._write_batch_to_file(batch, i)

    def write_quantity_to_file(self) -> int:
        """
        Write the quantity of batches to a file
        :return: Quantity of batches
        """
        logger.info(f"Write quantity {len(self.batches)} of batches to a file")
        quantity_file: Path = (
            Path(self.local_artifact_output)
            / self.batch_urls_directory
            / self.output_quantity_file
        )
        quantity_file.parent.mkdir(parents=True, exist_ok=True)

        with open(
            quantity_file,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(str(len(self.batches)))

        logger.info("Quantity of batches written")
        return len(self.batches)

    def _write_batch_to_file(self, batch: List[str], i: int) -> None:
        """
        Write a batch of documents ids to a file
        :param batch: List of documents ids
        :param i: Index of the batch
        :return: None
        """
        logger.info("Batch %s size: %s", i, len(batch))
        logger.info("Write batch %s", i)
        batch_file: Path = (
            Path(self.local_artifact_output)
            / self.batch_urls_directory
            / f"{str(i)}_{self.output_batch_file}"
        )
        batch_file.parent.mkdir(parents=True, exist_ok=True)

        with open(
            batch_file,
            "w",
        ) as f:
            spamwriter = csv.writer(
                f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
            )
            for docid in batch:
                spamwriter.writerow([docid])

        logger.info("%s batch written", i)
