from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from welearn_datastack.exceptions import DBIntegrityErrorObjectNotFound
from welearn_datastack.modules.write_data_safely_in_db import insert_batch_with_retry


class TestInsertBatchWithRetry(TestCase):
    def test_retry_removes_conflicting_object_and_rollbacks(self):
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        recorded_batches = []
        conflicting_id = uuid4()

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

    def test_retry_with_dict_params(self):
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        recorded_batches = []
        conflicting_id = uuid4()

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

    def test_raise_when_conflicting_object_not_found(self):
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        conflicting_id = uuid4()
        integrity_error = IntegrityError(
            "UPDATE ...",
            [{"document_related_welearn_document_id": conflicting_id}],
            Exception("duplicate key"),
        )
        integrity_error.args = (
            f"Key (document_related_welearn_document_id)=({conflicting_id}) already exists",
        )
        session.flush.side_effect = [integrity_error]

        with self.assertRaises(DBIntegrityErrorObjectNotFound):
            insert_batch_with_retry(
                session=session,
                objects=[SimpleNamespace(id=uuid4())],
                key_path="document_related_welearn_document_id",
                max_retries=1,
            )

        self.assertEqual(session.rollback.call_count, 1)
