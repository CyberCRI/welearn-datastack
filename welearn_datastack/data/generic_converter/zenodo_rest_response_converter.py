import datetime
from dataclasses import dataclass

from welearn_datastack.data.source_models.zenodo import ZenodoRecord


@dataclass
class ZenodoRestResponseConverter:
    def __init__(self, zenodo_record: ZenodoRecord):
        self.title = zenodo_record.title
        self.external_id = zenodo_record.conceptrecid
        self.doi = zenodo_record.conceptdoi
        self.description = zenodo_record.metadata.description

        pdf_url = None
        for file_url in zenodo_record.files:
            if file_url.key.endswith(".pdf"):
                pdf_url = file_url.links.self

        self.pdf_url = pdf_url
        self.creator_names = [x.name for x in zenodo_record.metadata.creators]
        self.access_right = zenodo_record.metadata.access_right

        self.publication_date = int(
            datetime.datetime.strptime(
                zenodo_record.metadata.publication_date, "%Y-%m-%d"
            ).timestamp()
        )

        self.update_date = int(
            datetime.datetime.strptime(
                zenodo_record.updated, "%Y-%m-%dT%H:%M:%S.%f"
            ).timestamp()
        )

        self.type = zenodo_record.metadata.resource_type.type
        self.licence = zenodo_record.metadata.license.id
        self.status = zenodo_record.status
