import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import (
    Base,
    Corpus,
    DocumentSlice,
    ProcessState,
    Sdg,
    WeLearnDocument,
)
from welearn_datastack.data.enumerations import Step
from welearn_datastack.nodes_workflow.DocumentClassifier import document_classifier
from welearn_datastack.utils_.virtual_environement_utils import (
    get_sub_environ_according_prefix,
)


class TestDocumentClassifier(unittest.TestCase):

    def setUp(self):
        get_sub_environ_according_prefix.cache_clear()
        os.environ["MODELS_PATH_ROOT"] = "test"

        self.engine = create_engine("sqlite://")
        s_maker = sessionmaker(self.engine)
        handle_schema_with_sqlite(self.engine)

        self.test_session = s_maker()
        Base.metadata.create_all(self.test_session.get_bind())

        corpus_source_name = "test_corpus"

        self.corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
        )

        self.doc_test_id = uuid.uuid4()
        self.doc_test = WeLearnDocument(
            id=self.doc_test_id,
            url="https://example.org",
            corpus_id=self.corpus_test.id,
            title="test",
            lang="en",
            full_content="test",
            description="test",
            details={"test": "test"},
            trace=1,
        )

        slice_test_id = uuid.uuid4()
        self.slice_test = DocumentSlice(
            id=slice_test_id,
            document_id=self.doc_test.id,
            embedding=numpy.array([1, 2, 3]),
            body="test",
            order_sequence=0,
            embedding_model_name="test",
            embedding_model_id=uuid.uuid4(),
        )

        self.test_sdg_id = uuid.uuid4()
        self.test_sdg_number = 1
        self.test_sdg = Sdg(
            id=self.test_sdg_id,
            slice_id=slice_test_id,
            sdg_number=self.test_sdg_number,
            bi_classifier_model_id=uuid4(),
            n_classifier_model_id=uuid4(),
        )

        self.test_session.add(self.corpus_test)
        self.test_session.add(self.doc_test)
        self.test_session.add(self.slice_test)

        self.test_session.commit()

        self.path_test_input = Path(__file__).parent.parent / "resources" / "input"
        self.path_test_input.mkdir(parents=True, exist_ok=True)

        os.environ["ARTIFACT_ROOT"] = self.path_test_input.parent.as_posix()

    def tearDown(self):
        self.test_session.close()
        del self.test_session

    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.n_classify_slices"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.bi_classify_slices"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.retrieve_models"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.retrieve_ids_from_csv"
    )
    def test_main(
        self,
        mock_retrieve_ids,
        mock_create_session,
        mock_retrieve_models,
        mock_bi_classify,
        mock_n_classify,
    ):
        mock_bi_classify.return_value = True
        mock_n_classify.return_value = [self.test_sdg]

        mock_retrieve_ids.return_value = [self.doc_test_id]
        session = self.test_session
        mock_create_session.return_value = session
        mock_retrieve_models.return_value = [Mock(lang="en", title="model_name")]
        document_classifier.main()

        state_in_db = session.query(ProcessState).all()

        # There is only one state by doc because the rest of steps were mocked
        self.assertEqual(state_in_db[0].title, Step.DOCUMENT_CLASSIFIED_SDG.value)

        sdg_in_db = session.query(Sdg).all()
        self.assertEqual(sdg_in_db[0].sdg_number, self.test_sdg_number)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.n_classify_slices"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.bi_classify_slices"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.retrieve_models"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.retrieve_ids_from_csv"
    )
    def test_main_bi_classifier_false(
        self,
        mock_retrieve_ids,
        mock_create_session,
        mock_retrieve_models,
        mock_bi_classify,
        mock_n_classify,
    ):
        mock_bi_classify.return_value = False

        # Should be useless but kept in case of bi classifier still
        # pass and avoid false positive (with an exception on n)
        mock_n_classify.return_value = [self.test_sdg]

        mock_retrieve_ids.return_value = [self.doc_test_id]
        session = self.test_session
        mock_create_session.return_value = session
        mock_retrieve_models.return_value = [Mock(lang="en", title="model_name")]
        document_classifier.main()

        state_in_db = session.query(ProcessState).all()

        # There is only one state by doc because the rest of steps were mocked
        self.assertEqual(state_in_db[0].title, Step.DOCUMENT_CLASSIFIED_NON_SDG.value)

    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.n_classify_slices"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.bi_classify_slices"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.retrieve_models"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.create_db_session"
    )
    @patch(
        "welearn_datastack.nodes_workflow.DocumentClassifier.document_classifier.retrieve_ids_from_csv"
    )
    def test_main_no_specific_sdg(
        self,
        mock_retrieve_ids,
        mock_create_session,
        mock_retrieve_models,
        mock_bi_classify,
        mock_n_classify,
    ):
        mock_bi_classify.return_value = True
        mock_n_classify.return_value = []

        mock_retrieve_ids.return_value = [self.doc_test_id]
        session = self.test_session
        mock_create_session.return_value = session
        mock_retrieve_models.return_value = [Mock(lang="en", title="model_name")]
        document_classifier.main()

        state_in_db = session.query(ProcessState).all()

        # There is only one state by doc because the rest of steps were mocked
        self.assertEqual(state_in_db[0].title, Step.DOCUMENT_CLASSIFIED_NON_SDG.value)
