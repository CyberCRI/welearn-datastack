from typing import Any, Optional

from pydantic import BaseModel, model_validator

from welearn_datastack.exceptions import NoDescriptionFoundError, NoTitle
from welearn_datastack.modules.xml_extractor import XMLExtractor


class RecordDates(BaseModel):
    dateAccessioned: Optional[str] = None
    dateAvailable: Optional[str] = None
    dateIssued: Optional[str] = None


class RecordIdentifier(BaseModel):
    uri: str
    doi: Optional[str] = None


class RecordFlocat(BaseModel):
    loctype: str
    type: str
    href: str


class RecordFile(BaseModel):
    id: str
    mimetype: str
    seq: str
    size: int
    checksum: str
    checksumtype: str
    admid: str
    groupid: str
    flocat: RecordFlocat


class WorldBankOKRRecord(BaseModel):
    authors: list[str]
    dates: RecordDates
    identifiers: RecordIdentifier
    abstract: str
    subjects: list[str]
    accessCondition: Optional[str] = None
    title: str
    fileGrp: list[RecordFile]

    @classmethod
    def _extract_file_grp(cls, value: XMLExtractor) -> list[dict]:
        ret = []
        try:
            file_grp = value.extract_content(tag="fileGrp")[0].content
        except IndexError as e:
            raise ValueError("Missing <fileGrp> tag in document") from e
        for f in XMLExtractor(file_grp).extract_content(tag="file"):
            f_ret = {k.lower(): v for k, v in f.attributes.items()}
            flocat_xml = XMLExtractor(f.content).extract_content(tag="FLocat")
            try:
                flocat_ret = {
                    k.lower().replace("xlink:", ""): v
                    for k, v in flocat_xml[0].attributes.items()
                }
            except IndexError as e:
                raise ValueError(
                    "Missing <FLocat> tag in <file>; cannot determine file address"
                ) from e

            if not flocat_ret.get("href"):
                raise ValueError(
                    "Missing xlink:href on <FLocat>; cannot determine file address"
                )

            f_ret["flocat"] = flocat_ret
            ret.append(f_ret)
        return ret

    @classmethod
    def _extract_dates(cls, value: XMLExtractor) -> dict:
        date_types = [
            "mods:dateAccessioned",
            "mods:dateAvailable",
            "mods:dateIssued",
        ]
        v = {}
        for dt in date_types:
            d = value.extract_content(tag=dt)
            if len(d) > 0:
                dt_name = dt.replace("mods:", "")
                v[dt_name] = d[0].content
        return v

    @classmethod
    def _extract_identifiers(cls, value: XMLExtractor) -> dict[str, str | None]:
        try:
            uri = value.extract_content_attribute_filter(
                tag="mods:identifier", attribute_name="type", attribute_value="uri"
            )[0].content
        except IndexError as e:
            raise ValueError('Missing <mods:identifier type="uri"> in document') from e

        if not uri:
            raise ValueError('Empty <mods:identifier type="uri"> in document')
        doi_items = value.extract_content_attribute_filter(
            tag="mods:identifier", attribute_name="type", attribute_value="doi"
        )
        doi = doi_items[0].content if doi_items else None
        return {"uri": uri, "doi": doi}

    @model_validator(mode="before")
    @classmethod
    def support_xml_extractor(cls, value: Any) -> Any:
        if isinstance(value, XMLExtractor):
            value: XMLExtractor

            try:
                title = value.extract_content(tag="mods:title")[0].content
            except IndexError:
                raise ValueError("No title in this document")

            _authors = [a.content for a in value.extract_content(tag="mods:namePart")]
            _subjects = [s.content for s in value.extract_content(tag="mods:topic")]
            try:
                _access_condition = value.extract_content(tag="mods:accessCondition")[
                    0
                ].content
            except IndexError:
                _access_condition = None

            try:
                _abstract = value.extract_content(tag="mods:abstract")[0].content
            except IndexError:
                raise ValueError("No abstract in this document")

            ret = {
                "authors": _authors,
                "dates": cls._extract_dates(value),
                "identifiers": cls._extract_identifiers(value),
                "abstract": _abstract,
                "subjects": _subjects,
                "accessCondition": _access_condition,
                "fileGrp": cls._extract_file_grp(value),
                "title": title,
            }
            return ret
        else:
            return value
