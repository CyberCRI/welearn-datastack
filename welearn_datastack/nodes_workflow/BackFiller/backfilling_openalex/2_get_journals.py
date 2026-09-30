import os
import sqlite3
import uuid
from itertools import batched

import requests
from dotenv import load_dotenv

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

    response = requests.get(url, params=querystring)
    response.raise_for_status()

    results = response.json()["results"]

    oa_ids = [i["ids"]["openalex"] for i in results]
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
    add_journals_columns()
    docdatas = get_docdata_from_work_db()
    journals = []
    for batch in batched(docdatas, n=100):
        journals.extend(get_data_from_open_alex([d[0] for d in batch]))

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for journal in journals:
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


if __name__ == "__main__":
    main()
