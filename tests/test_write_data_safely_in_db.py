from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.exceptions import (
    DBIntegrityErrorObjectNotFound,
    DBIntegrityErrorParamKeyNotFound,
    InvalidIDFormat,
)
from welearn_datastack.modules.write_data_safely_in_db import (
    extract_faulty_key_name_and_value,
    extract_id_from_exception,
    insert_batch_with_retry,
)


class TestInsertBatchWithRetry(TestCase):
    @patch(
        "welearn_datastack.modules.write_data_safely_in_db.extract_id_from_exception"
    )
    def test_retry_removes_conflicting_object_and_rollbacks(
        self, mock_extract_id_from_exception
    ):
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        recorded_batches = []
        conflicting_id = uuid4()
        mock_extract_id_from_exception.return_value = conflicting_id

        def _record_batch(batch):
            recorded_batches.append(list(batch))

        session.add_all.side_effect = _record_batch
        integrity_error = IntegrityError(
            "UPDATE ...",
            [{"document_related_welearn_document_id": conflicting_id}],
            Exception("duplicate key"),
        )
        integrity_error.args = (
            f"Key (document_related_welearn_document_id)=({conflicting_id}) already exists",
        )
        session.flush.side_effect = [
            integrity_error,
            None,
        ]

        conflicting_object = SimpleNamespace(id=conflicting_id)
        valid_object = SimpleNamespace(id=uuid4())

        failed = insert_batch_with_retry(
            session=session,
            objects=[conflicting_object, valid_object],
            key_path="document_related_welearn_document_id",
            max_retries=5,
        )

        self.assertEqual(failed, [conflicting_id])
        self.assertEqual(session.rollback.call_count, 1)

        # First attempt with both objects, second attempt without the conflicting one.
        self.assertEqual(session.add_all.call_count, 2)
        self.assertEqual(recorded_batches[0], [conflicting_object, valid_object])
        self.assertEqual(recorded_batches[1], [valid_object])

    @patch(
        "welearn_datastack.modules.write_data_safely_in_db.extract_id_from_exception"
    )
    def test_retry_with_dict_params(self, mock_extract_id_from_exception):
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        recorded_batches = []
        conflicting_id = uuid4()
        mock_extract_id_from_exception.return_value = conflicting_id

        def _record_batch(batch):
            recorded_batches.append(list(batch))

        session.add_all.side_effect = _record_batch
        integrity_error = IntegrityError(
            "UPDATE ...",
            {"document_related_welearn_document_id": conflicting_id},
            Exception("duplicate key"),
        )
        integrity_error.args = (
            f"Key (document_related_welearn_document_id)=({conflicting_id}) already exists",
        )
        session.flush.side_effect = [integrity_error, None]

        conflicting_object = SimpleNamespace(id=conflicting_id)
        valid_object = SimpleNamespace(id=uuid4())

        failed = insert_batch_with_retry(
            session=session,
            objects=[conflicting_object, valid_object],
            key_path="document_related_welearn_document_id",
            max_retries=2,
        )

        self.assertEqual(failed, [conflicting_id])
        self.assertEqual(session.rollback.call_count, 1)
        self.assertEqual(recorded_batches[1], [valid_object])

    @patch(
        "welearn_datastack.modules.write_data_safely_in_db.extract_id_from_exception"
    )
    @patch(
        "welearn_datastack.modules.write_data_safely_in_db._extract_culprit_document"
    )
    def test_raise_when_conflicting_object_not_found(
        self, mock_extract_culprit_document, mock_extract_id_from_exception
    ):
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        conflicting_id = uuid4()
        integrity_error = IntegrityError(
            statement="UPDATE ...",
            params=[{"document_related_welearn_document_id": conflicting_id}],
            orig=Exception("duplicate key"),
        )
        integrity_error.args = (
            f"Key (document_related_welearn_document_id)=({conflicting_id}) already exists",
        )
        session.flush.side_effect = [integrity_error]

        mock_extract_culprit_document.return_value = WeLearnDocument(
            id=conflicting_id,
        )

        mock_extract_id_from_exception.return_value = conflicting_id

        with self.assertRaises(DBIntegrityErrorObjectNotFound):
            insert_batch_with_retry(
                session=session,
                objects=[SimpleNamespace(id=uuid4())],
                key_path="document_related_welearn_document_id",
                max_retries=1,
            )

        self.assertEqual(session.rollback.call_count, 1)

    def test_extract_faulty_key_name_and_value(self):
        stmt_msg = '(psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "welearn_document_trace_unique"\nDETAIL:  Key (trace)=(655384981) already exists.\n'
        tested_exception = IntegrityError(
            statement=stmt_msg,
            params=[{"trace": 655384981}],
            orig=Exception(stmt_msg),
        )
        awaited_ret = "trace", "655384981"

        ret = extract_faulty_key_name_and_value(tested_exception)
        self.assertEqual(awaited_ret, ret)

    def test_extract_faulty_key_name_and_value_error(self):
        stmt_msg = "(psycopg2.errors.OtherProblem) Other problem"
        tested_exception = IntegrityError(
            statement=stmt_msg,
            params=[],
            orig=Exception(stmt_msg),
        )

        ret = extract_faulty_key_name_and_value(tested_exception)
        self.assertIsNone(ret)

    def test_extract_id_from_exception(self):
        doc_id = uuid4()
        stmt_msg = '(psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "welearn_document_trace_unique"\nDETAIL:  Key (trace)=(655384981) already exists.\n'
        tested_exception = IntegrityError(
            statement=stmt_msg,
            params=[
                {
                    "trace": 655384981,
                    "document_related_welearn_document_id": str(doc_id),
                },
                {
                    "trace": 555381234,
                    "document_related_welearn_document_id": str(uuid4()),
                },
            ],
            orig=Exception(stmt_msg),
        )
        awaited_ret = doc_id
        ret = extract_id_from_exception(
            tested_exception, key_path="document_related_welearn_document_id"
        )

        self.assertEqual(awaited_ret, ret)

    def test_extract_id_from_exception_exception_DBIntegrityErrorParamKeyNotFound(self):
        doc_id = uuid4()
        stmt_msg = "(psycopg2.errors.OtherProblem) Other problem"
        tested_exception = IntegrityError(
            statement=stmt_msg,
            params=[
                {
                    "trace": 655384981,
                    "document_related_welearn_document_id": str(doc_id),
                },
                {
                    "trace": 555381234,
                    "document_related_welearn_document_id": str(uuid4()),
                },
            ],
            orig=Exception(stmt_msg),
        )
        with self.assertRaises(DBIntegrityErrorParamKeyNotFound):
            extract_id_from_exception(
                tested_exception, key_path="document_related_welearn_document_id"
            )

    def test_extract_id_from_exception_exception_DBIntegrityErrorParamKeyNotFound2(
        self,
    ):
        doc_id = uuid4()
        stmt_msg = '(psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "welearn_document_trace_unique"\nDETAIL:  Key (trace)=(655384981) already exists.\n'
        tested_exception = IntegrityError(
            statement=stmt_msg,
            params=[
                {
                    "trace": 655384981,
                    "no_document_related_welearn_document_id": str(doc_id),
                },
                {
                    "trace": 555381234,
                    "no_document_related_welearn_document_id": str(uuid4()),
                },
            ],
            orig=Exception(stmt_msg),
        )
        with self.assertRaises(DBIntegrityErrorParamKeyNotFound):
            extract_id_from_exception(
                tested_exception, key_path="document_related_welearn_document_id"
            )

    def test_extract_id_from_exception_InvalidIDFormat(self):
        doc_id = 1
        stmt_msg = '(psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "welearn_document_trace_unique"\nDETAIL:  Key (trace)=(655384981) already exists.\n'
        tested_exception = IntegrityError(
            statement=stmt_msg,
            params=[
                {
                    "trace": 655384981,
                    "document_related_welearn_document_id": str(doc_id),
                },
                {
                    "trace": 555381234,
                    "document_related_welearn_document_id": str(2),
                },
            ],
            orig=Exception(stmt_msg),
        )

        with self.assertRaises(InvalidIDFormat):
            extract_id_from_exception(
                tested_exception, key_path="document_related_welearn_document_id"
            )
