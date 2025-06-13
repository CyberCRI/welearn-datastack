import csv
import json
import os
import random
import shutil
import string
import uuid
from pathlib import Path
from typing import Dict, List, Tuple
from unittest import TestCase, mock

from sqlalchemy import create_engine
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sympy.integrals.meijerint_doc import category

from tests.database_test_utils import handle_schema_with_sqlite
from welearn_datastack.data.db_models import (
    Base,
    Corpus,
    ProcessState,
    WeLearnDocument,
    Category,
)
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.modules import collector_selector
from welearn_datastack.nodes_workflow.DocumentHubCollector import document_collector
from welearn_datastack.plugins.interface import IPluginFilesCollector


def random_string(length: int):
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, k=length)  # nosec
    )


corpus_source_name = "test_corpus"
list_of_swld = [
    ScrapedWeLearnDocument(
        document_title=random_string(20),
        document_url="https://example.org/wiki/Randomness",
        document_lang="en",
        document_content=random_string(300),
        document_desc=random_string(100),
        document_corpus=corpus_source_name,
        document_details={
            random_string(5): random_string(20),
            random_string(5): random_string(20),
            random_string(5): random_string(20),
            random_string(5): random_string(20),
        },
    ),
    ScrapedWeLearnDocument(
        document_title=random_string(20),
        document_url="https://example.org/wiki/Unit_testing",
        document_lang="en",
        document_content=random_string(300),
        document_desc=random_string(100),
        document_corpus=corpus_source_name,
        document_details={
            random_string(5): random_string(20),
            random_string(5): random_string(20),
            random_string(5): random_string(20),
            random_string(5): random_string(20),
        },
    ),
]

dict_url_for_doc = {doc.document_url: doc for doc in list_of_swld}


class TestPluginFiles(IPluginFilesCollector):
    related_corpus: str = corpus_source_name

    def __init__(self):
        super().__init__()

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        res: List[ScrapedWeLearnDocument] = []
        errors_urls: List[str] = []
        try:
            for doc in list_of_swld:
                if doc.document_url in urls:
                    res.append(dict_url_for_doc[doc.document_url])
        except Exception as e:
            errors_urls.append(urls[0])
        return res, errors_urls


class TestExtractNCollectDocs(TestCase):
    def setUp(self) -> None:
        os.environ["PG_DRIVER"] = "sqlite"
        os.environ["PG_USER"] = ""
        os.environ["PG_PASSWORD"] = ""  # nosec
        os.environ["PG_HOST"] = ""
        os.environ["PG_DB"] = ":memory:"

        self.engine = create_engine("sqlite://")
        s_maker = sessionmaker(self.engine)
        handle_schema_with_sqlite(self.engine)

        self.test_session = s_maker()
        Base.metadata.create_all(self.test_session.get_bind())

        collector_selector.plugins_files_list = [TestPluginFiles]

        self.path_test_input = Path(__file__).parent.parent / "resources" / "input"
        self.path_test_input.mkdir(parents=True, exist_ok=True)

        os.environ["ARTIFACT_ROOT"] = self.path_test_input.parent.as_posix()
        self.category_name = "categroy_test0"

        self.category_id = uuid.uuid4()

        self.category = Category(id=self.category_id, title=self.category_name)

        self.test_session.add(self.category)

        self.corpus_test = Corpus(
            id=uuid.uuid4(),
            source_name=corpus_source_name,
            is_fix=True,
            is_active=True,
            category_id=self.category_id,
        )

        self.test_session.add(self.corpus_test)
        self.test_session.commit()

    def tearDown(self) -> None:
        self.test_session.close()
        del self.test_session
        shutil.rmtree(self.path_test_input, ignore_errors=True)
        shutil.rmtree(self.path_test_input.parent / "output", ignore_errors=True)

    def test_extract_data(self):
        url_0 = list_of_swld[0].document_url
        url_1 = list_of_swld[1].document_url

        wd0 = WeLearnDocument(id=uuid.uuid4(), url=url_0, corpus=self.corpus_test)

        wd1 = WeLearnDocument(id=uuid.uuid4(), url=url_1, corpus=self.corpus_test)
        self.test_session.add(wd0)
        self.test_session.add(wd1)
        self.test_session.commit()

        (
            extracted_docs,
            error_docs,
            process_states,
        ) = document_collector.extract_data_from_urls(welearn_documents=[wd0, wd1])

        self.assertEqual(len(extracted_docs), 2)
        self.assertEqual(len(error_docs), 0)
        self.assertEqual(len(process_states), 2)

    def test_extract_data_corpus_not_found(self):
        url_0 = list_of_swld[0].document_url
        url_1 = list_of_swld[1].document_url

        wd0 = WeLearnDocument(id=uuid.uuid4(), url=url_0, corpus=self.corpus_test)

        wd1 = WeLearnDocument(
            id=uuid.uuid4(),
            url=url_1,
            corpus_id=uuid.uuid4(),
        )
        self.test_session.add(wd0)
        self.test_session.add(wd1)

        self.test_session.commit()
        (
            extracted_docs,
            error_docs,
            process_states,
        ) = document_collector.extract_data_from_urls(welearn_documents=[wd0, wd1])

        self.assertEqual(len(extracted_docs), 1)
        self.assertEqual(len(process_states), 1)

    @mock.patch(
        "welearn_datastack.nodes_workflow.DocumentHubCollector.document_collector.create_db_session"
    )
    def test_main(self, create_db_session_mock):
        create_db_session_mock.return_value = self.test_session
        uuids = [uuid.uuid4() for _ in range(2)]
        wd0 = WeLearnDocument(
            id=uuids[0], url=list_of_swld[0].document_url, corpus=self.corpus_test
        )
        wd1 = WeLearnDocument(
            id=uuids[1], url=list_of_swld[1].document_url, corpus=self.corpus_test
        )
        self.test_session.add(wd0)
        self.test_session.add(wd1)
        self.test_session.commit()

        with (self.path_test_input / "batch_ids.csv").open("w") as f:
            writer = csv.writer(f)
            for uuid_ in uuids:
                writer.writerow([uuid_])

        document_collector.main()

        # Get data from database and check
        for uuid_ in uuids:
            current_doc = (
                self.test_session.query(WeLearnDocument)
                .filter(WeLearnDocument.id == uuid_)
                .one()
            )

            self.assertEqual(current_doc.corpus_id, self.corpus_test.id)
            self.assertEqual(current_doc.corpus.source_name, corpus_source_name)

        self.assertEqual(
            len(
                list(
                    self.test_session.query(ProcessState).filter(
                        ProcessState.document_id.in_(uuids)
                    )
                )
            ),
            2,
        )

    # /!\ This filter is not used anymore /!\
    # def test_filter_already_update(self):
    #     """
    #     Check if the method correctly ignore already updated documents in database
    #     :return:
    #     """
    #     states = []
    #     wd0 = WeLearnDocument(
    #         id=uuid.uuid4(),
    #         url=list_of_swld[0].document_url,
    #         corpus=self.corpus_test,
    #         title=list_of_swld[0].document_title,
    #         lang=list_of_swld[0].document_lang,
    #         full_content=list_of_swld[0].document_content,
    #         description=list_of_swld[0].document_desc,
    #         details=list_of_swld[0].document_details,
    #         trace=list_of_swld[0].trace,
    #     )
    #     wd1 = WeLearnDocument(
    #         id=uuid.uuid4(),
    #         url=list_of_swld[1].document_url,
    #         corpus=self.corpus_test,
    #     )
    #     ret = []
    #
    #     self.test_session.add(wd0)
    #     self.test_session.add(wd1)
    #     self.test_session.commit()
    #
    #     document_collector.handle_scraped_docs(
    #         scraped_docs=list_of_swld,
    #         states=states,
    #         ret_documents=ret,
    #         doc_db_urls_dict={x.url: x for x in [wd0, wd1]},
    #     )
    #
    #     self.assertEqual(len(ret), 1)
    #     self.assertEqual(len(states), 1)
