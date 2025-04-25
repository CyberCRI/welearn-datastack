import sqlalchemy
from sqlalchemy import Engine

from welearn_datastack.data.db_models import DbSchemaEnum


# Function from :
# https://stackoverflow.com/questions/66208938/sqlalchemy-exc-operationalerror-sqlite3-operationalerror-unknown-database-my
def handle_schema_with_sqlite(db_engine: Engine):
    """
    Create the schema for the sqlite database in memory
    :param db_engine:  The database engine
    :return:
    """
    with db_engine.begin() as conn:
        for schema_name in DbSchemaEnum:  # type: ignore
            conn.execute(sqlalchemy.text(f"ATTACH ':memory:' AS {schema_name.value}"))
