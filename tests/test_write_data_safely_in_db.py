import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from welearn_database.data.models import Base, Category, Corpus, WeLearnDocument

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.modules.write_data_safely_in_db import insert_batch_safely


class TestInsertBatchSafely(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        handle_schema_with_sqlite(self.engine)
        self.session = sessionmaker(self.engine)()
        Base.metadata.create_all(self.session.get_bind())

        self.category = Category(id=uuid.uuid4(), title="test-category")
        self.corpus = Corpus(
            id=uuid.uuid4(),
            source_name="test-corpus",
            is_fix=True,
            is_active=True,
            category_id=self.category.id,
        )
        self.session.add_all([self.category, self.corpus])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _make_document(self, *, doc_id=None, url: str, title: str):
        return WeLearnDocument(
            id=doc_id or uuid.uuid4(),
            url=url,
            corpus_id=self.corpus.id,
            title=title,
            lang="en",
            description="description",
            full_content="content long enough for validation",
            details={"source": "test"},
        )

    def test_returns_empty_list_for_empty_batch(self):
        failed = insert_batch_safely(self.session, [])

        self.assertEqual(failed, [])

    def test_inserts_documents_already_attached_to_session(self):
        first_doc = self._make_document(url="https://example.org/1", title="doc-1")
        second_doc = self._make_document(url="https://example.org/2", title="doc-2")
        self.session.add_all([first_doc, second_doc])

        failed = insert_batch_safely(self.session, [first_doc, second_doc])
        self.session.commit()

        persisted_ids = {
            doc.id
            for doc in self.session.query(WeLearnDocument)
            .order_by(WeLearnDocument.url)
            .all()
        }

        self.assertEqual(failed, [])
        self.assertEqual(persisted_ids, {first_doc.id, second_doc.id})

    def test_returns_conflicting_document_id_and_keeps_other_documents(self):
        existing_doc = self._make_document(
            doc_id=uuid.uuid4(),
            url="https://example.org/already-there",
            title="existing",
        )
        self.session.add(existing_doc)
        self.session.commit()

        conflicting_doc = self._make_document(
            doc_id=uuid.uuid4(),
            url="https://example.org/already-there",
            title="duplicate",
        )
        valid_doc = self._make_document(
            doc_id=uuid.uuid4(),
            url="https://example.org/new",
            title="valid",
        )

        failed = insert_batch_safely(self.session, [conflicting_doc, valid_doc])
        self.session.commit()

        persisted_docs = (
            self.session.query(WeLearnDocument).order_by(WeLearnDocument.url).all()
        )
        persisted_urls = [doc.url for doc in persisted_docs]
        persisted_ids = {doc.id for doc in persisted_docs}

        self.assertEqual(failed, [conflicting_doc.id])
        self.assertEqual(
            persisted_urls,
            ["https://example.org/already-there", "https://example.org/new"],
        )
        self.assertIn(valid_doc.id, persisted_ids)
        self.assertNotIn(conflicting_doc.id, persisted_ids)

    def test_handles_duplicates_inside_same_batch(self):
        first_doc = self._make_document(
            doc_id=uuid.uuid4(),
            url="https://example.org/shared",
            title="first",
        )
        duplicate_doc = self._make_document(
            doc_id=uuid.uuid4(),
            url="https://example.org/shared",
            title="duplicate",
        )
        valid_doc = self._make_document(
            doc_id=uuid.uuid4(),
            url="https://example.org/unique",
            title="valid",
        )

        failed = insert_batch_safely(
            self.session, [first_doc, duplicate_doc, valid_doc]
        )
        self.session.commit()

        persisted_docs = (
            self.session.query(WeLearnDocument).order_by(WeLearnDocument.url).all()
        )
        persisted_ids = {doc.id for doc in persisted_docs}

        self.assertEqual(failed, [duplicate_doc.id])
        self.assertIn(first_doc.id, persisted_ids)
        self.assertIn(valid_doc.id, persisted_ids)
        self.assertNotIn(duplicate_doc.id, persisted_ids)
