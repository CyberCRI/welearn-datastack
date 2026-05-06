import tempfile
import unittest
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import TextClause

from welearn_datastack.modules.query_utils import (
    resolve_batched_query,
    resolve_query,
    resolve_query_on_given_ids,
)


def create_temp_sql_file(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sql", mode="w")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


class TestQueryUtils(unittest.TestCase):
    def test_resolve_query_with_batch_size(self):
        sql = "SELECT * FROM table WHERE id=:revision_id LIMIT :batch_size"
        sql_path = create_temp_sql_file(sql)
        batch_size = 10
        revision_id = "abc123de"
        stmt = resolve_batched_query(
            batch_size, sql_path.parent, sql_path.name, revision_id
        )
        self.assertIsInstance(stmt, TextClause)
        compiled = stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
        self.assertIn(f"LIMIT {batch_size}", str(compiled))
        self.assertIn(f"WHERE id='{revision_id}'", str(compiled))

    def test_resolve_query_without_batch_size(self):
        sql = "SELECT * FROM table WHERE id=:revision_id"
        sql_path = create_temp_sql_file(sql)
        revision_id = "abc"
        stmt = resolve_query(sql_path.parent, sql_path.name, revision_id)
        self.assertIsInstance(stmt, TextClause)
        compiled = stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
        self.assertIn(f"WHERE id='{revision_id}'", str(compiled))

    def test_missing_param_raises(self):
        sql = "SELECT * FROM table WHERE id=:revision_id"  # missing :batch_size
        sql_path = create_temp_sql_file(sql)
        with self.assertRaises(ValueError):
            resolve_batched_query(10, sql_path.parent, sql_path.name, "abc")

    def test_missing_revision_id_raises(self):
        sql = "SELECT * FROM table WHERE id=:revision_id"
        sql_path = create_temp_sql_file(sql)
        with self.assertRaises(ValueError):
            resolve_query(sql_path.parent, sql_path.name, None)

    def test_resolve_query_on_given_ids(self):
        sql = "SELECT * FROM table WHERE id IN :ids AND revision_id = :revision_id"
        sql_path = create_temp_sql_file(sql)
        ids = [1, 2, 3]
        revision_id = "abc"
        stmt = resolve_query_on_given_ids(
            ids, sql_path.parent, sql_path.name, revision_id
        )
        self.assertIsInstance(stmt, TextClause)
        compiled = stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
        self.assertIn(f"revision_id = '{revision_id}'", str(compiled))
        txt_lst = str(ids).replace("[", "(").replace("]", ")")
        self.assertIn(f"id IN {txt_lst}", str(compiled))
