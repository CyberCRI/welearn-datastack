import logging
import os

import pydantic
import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack import constants
from welearn_datastack.constants import (
    AUTHORIZED_LICENSES,
    ZENODO_API_BASE_URL,
    ZENODO_APPLICATION_BASE_URL,
)
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.generic_converter.zenodo_rest_response_converter import (
    ZenodoRestResponseConverter,
)
from welearn_datastack.data.source_models.zenodo import ZenodoRecord
from welearn_datastack.exceptions import (
    ClosedAccessContent,
    LegalException,
    NotEnoughData,
    NotExpectedAmountOfItems,
    UnauthorizedLicense,
    WrongFormat,
)
from welearn_datastack.modules.pdf_extractor import get_pdf_content
from welearn_datastack.modules.scraping_utils import clean_text, format_cc_license
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)

logger = logging.getLogger(__name__)


# Collector
class IPBESCollector(IPluginRESTCollector):
    related_corpus = "ipbes"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

        self.api_base_url = (
            "https://data.unesco.org/api/explore/v2.1/catalog/datasets/doc001"
        )
        self.application_base_url = ZENODO_APPLICATION_BASE_URL
        self.api_base_url = ZENODO_API_BASE_URL
        self.headers = constants.HEADERS
        self.pdf_size_file_limit: int = int(os.getenv("PDF_SIZE_FILE_LIMIT", 2000000))

    @staticmethod
    def _extract_authors(metadata: ZenodoRestResponseConverter) -> list[AuthorDetails]:
        ret: list[AuthorDetails] = [
            AuthorDetails(name=a, misc="") for a in metadata.creator_names
        ]
        return ret

    @staticmethod
    def _check_usage_authorization(ipbes_record: ZenodoRestResponseConverter) -> None:
        if ipbes_record.access_right != "open":
            raise ClosedAccessContent(
                f"Document {ipbes_record.external_id} is not open access, access_right={ipbes_record.access_right}"
            )

        license_url = format_cc_license(ipbes_record.licence)

        if license_url not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"License '{license_url}' is not authorized.")

    def _get_zenodo_rest_json(self, document: WeLearnDocument) -> ZenodoRecord:
        """
        Get the metadata of a document from the IPBES API, using the document external_id as a search query.
         The metadata is returned as a IPBESItem object.
         If no document is found, a ValueError is raised.
         If more than one document is found, only the first one is returned and a warning is logged.
         The search query is made on the url field of the IPBES API, which contains the external_id of the document in the format "ark:/12345/abcde" or "ark:/12345/abcde/lang".
         :param document: WeLearnDocument object containing the external_id to search for in the IPBES API.
         :return: IPBESItem object containing the metadata of the document.
         :raises NotEnoughData: If no document is found for the given external_id.
         :raises requests.exceptions.RequestException: If there is an error while making the HTTP request to the IPBES API.
         :raises pydantic.ValidationError: If there is an error while validating the response from the IPBES API against the IPBESRoot model.
        :raises NotExpectedMoreThanOneItem: If there is more or less results than expected for the given external_id.
        """
        session = get_new_https_session()

        resp = session.get(f"{self.api_base_url}{document.external_id}")
        resp.raise_for_status()
        record = ZenodoRecord.model_validate(resp.json())

        return record

    def _transform_converter_to_welearn_document(
        self,
        welearn_document: WeLearnDocument,
        lite_record: ZenodoRestResponseConverter,
    ) -> WeLearnDocument:
        """
        Transform a ZenodoRestResponseConverter object to a WeLearnDocument object.
        :param lite_record: ZenodoRestResponseConverter object to transform.
        :return: WeLearnDocument object.
        """
        welearn_document.external_id = lite_record.external_id
        welearn_document.doi = lite_record.doi
        welearn_document.title = lite_record.title
        welearn_document.description = clean_text(lite_record.description)
        welearn_document.corpus_name = self.corpus_name
        details = (
            {
                "authors": self._extract_authors(lite_record),
                "publication_date": lite_record.publication_date,
                "update_date": lite_record.update_date,
                "type": lite_record.type,
                "license": format_cc_license(lite_record.licence),
                "status": lite_record.status,
            },
        )
        welearn_document.details = details

        return welearn_document

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        for document in documents:
            try:

                record = self._get_zenodo_rest_json(document=document)
                lite_record = ZenodoRestResponseConverter(record)

                self._check_usage_authorization(lite_record)

                document = self._transform_converter_to_welearn_document(
                    welearn_document=document, lite_record=lite_record
                )

            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving IPBES ({document.url}) document from this url {self.api_base_url}/resources/{document.external_id}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except pydantic.ValidationError as e:
                msg = f"Error while validating IPBES ({document.url}) document from this url {self.api_base_url}/resources/{document.external_id} : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue
            except NotEnoughData as e:
                msg = f"Not enough data to retrieve document {document.url} from IPBES : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue
            except NotExpectedAmountOfItems as e:
                msg = f"Not expected this amount item for document {document.url} from IPBES : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue
            except LegalException as e:
                msg = f"Legal exception for document {document.url} from IPBES : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue
            except WrongFormat as e:
                msg = f"Formatting error in {document.url} from IPBES : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            ret.append(WrapperRetrieveDocument(document=document))

        return ret
