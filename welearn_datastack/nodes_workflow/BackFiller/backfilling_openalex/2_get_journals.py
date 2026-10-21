import logging
import os
import sqlite3
import uuid
from itertools import batched

import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
DB_FILE = os.getenv("DB_FILE", "work.db")


def add_journals_columns():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""ALTER TABLE document_id ADD COLUMN journal_name TEXT""")
    except sqlite3.OperationalError:
        print("La colonne 'journal_name' existe déjà")

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""ALTER TABLE document_id ADD COLUMN journal_id TEXT""")
    except sqlite3.OperationalError:
        print("La colonne 'journal_id' existe déjà")


def get_data_from_open_alex(urls: list[str]):
    url = "https://api.openalex.org/works"

    querystring = {
        "filter": f"ids.openalex:{'|'.join(urls)}",
        "per_page": len(urls),
        "select": "best_oa_location,id",
    }

    response = requests.get(url, params=querystring, timeout=120)
    response.raise_for_status()

    results = response.json()["results"]

    oa_ids = [i["id"] for i in results]
    ret = []

    for u in urls:
        if u not in oa_ids:
            ret.append((u, "", ""))

    for r in results:
        try:
            local_id = r["id"]
            journal_name = r["best_oa_location"]["source"]["display_name"]
            journal_oa_id = r["best_oa_location"]["source"]["id"]
        except TypeError as e:
            journal_name = ""
        ret.append(
            (local_id, journal_name, str(uuid.uuid5(uuid.NAMESPACE_URL, journal_oa_id)))
        )

    return ret


def get_docdata_from_work_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        docdatas = cursor.execute(
            "SELECT document_url FROM document_id WHERE journal_name IS NULL"
        )
    return docdatas.fetchall()


def format_journal_name(name: str):
    return name.lower().replace(" ", "-")


def main():
    logger.info("=" * 60)
    logger.info("FETCHING JOURNALS FROM OPENALEX")
    logger.info("=" * 60)

    add_journals_columns()
    docdatas = get_docdata_from_work_db()
    logger.info(f"Found {len(docdatas)} documents without journal info")

    if not docdatas:
        logger.info("No documents to process")
        return

    journals = []
    batch_number = 0

    for batch in batched(docdatas, n=100):
        batch_number += 1
        logger.info(
            f"Processing batch {batch_number} ({len(list(batch))} documents)..."
        )
        batch_list = list(batch)
        batch_result = get_data_from_open_alex([d[0] for d in batch_list])
        journals.extend(batch_result)
        logger.info(
            f"✓ Batch {batch_number} complete: {len(batch_result)} journals fetched"
        )

    logger.info(f"Total journals extracted: {len(journals)}")

    updated_count = 0
    error_count = 0

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for journal in journals:
            try:
                sql = "UPDATE document_id SET journal_name= ?, journal_id = ? WHERE document_url = ?"
                cursor.execute(
                    sql,
                    (
                        format_journal_name(journal[1]),
                        journal[2],
                        journal[0],
                    ),
                )
                conn.commit()
                updated_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating journal for {journal[0]}: {str(e)}")

    logger.info("=" * 60)
    logger.info(f"JOURNAL UPDATE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total processed: {len(journals)}")
    logger.info(f"Successfully updated: {updated_count} ✓")
    logger.info(f"Failed: {error_count} ✗")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
