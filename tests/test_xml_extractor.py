import unittest
from pathlib import Path

from welearn_datastack.data.xml_data import XMLData
from welearn_datastack.modules.xml_extractor import XMLExtractor


class TestXMLExtractor(unittest.TestCase):
    def setUp(self):
        """Set up example XML data for tests."""
        self.simple_xml = """
        <root>
            <title>Learn Python</title>
            <author>John Doe</author>
        </root>
        """
        self.complex_xml = """
        <root>
            <book id="1" genre="tech">
                <title>Learn Python</title>
                <author>John Doe</author>
            </book>
            <book id="2" genre="tech">
                <title>Introduction to XML</title>
                <author>Marie Curie</author>
            </book>
            <note importance="high">This is a sample document.</note>
        </root>
        """
        self.empty_content_xml = """
        <root>
            <title></title>
            <author>   </author>
        </root>
        """
        self.no_matching_tag_xml = """
        <root>
            <chapter>Introduction</chapter>
        </root>
        """

        self.xml_mets = """
        <mets:dmdSec ID="MD_OB_obp_14432" >
            <mets:mdWrap MDTYPE="DC" LABEL="Dublin Core Descriptive Metadata" MIMETYPE="text/xml" >
                <mets:xmlData>
                    <dcterms:identifier scheme="URI" >https://books.openedition.org/obp/14432</dcterms:identifier>
                    <dcterms:language xsi:type="dcterms:RFC1766" >en</dcterms:language>
                    <dcterms:created xsi:type="dcterms:W3CDTF" >2020</dcterms:created>
                    <dcterms:issued xsi:type="dcterms:W3CDTF" >2021-04-06T00:00:00Z</dcterms:issued>
                    <dcterms:accessRights>info:eu-repo/semantics/openAccess</dcterms:accessRights>
                    <dcterms:type>book</dcterms:type>
                    <dcterms:rights>https://creativecommons.org/licenses/by/4.0/</dcterms:rights>
                    <dcterms:title>Simplified Signs: A Manual Sign-Communication System for Special. Volume 1</dcterms:title>
                    <dcterms:publisher>Open Book Publishers</dcterms:publisher>
                    <dcterms:isPartOf xsi:type="dcterms:URI" >https://books.openedition.org/obp</dcterms:isPartOf>
                    <dcterms:extent>xxiv-621</dcterms:extent>
                    <dcterms:source>This digital publication is the result of automatic optical character recognition.</dcterms:source>
                    <dcterms:creator>Bonvillian, John D.</dcterms:creator>
                    <dcterms:creator>Lee, Nicole Kissane</dcterms:creator>
                    <dcterms:creator>Dooley, Tracy T.</dcterms:creator>
                    <dcterms:creator>Loncke, Filip T.</dcterms:creator>
                    <dcterms:creator>Nelson-Metlay, Valerie</dcterms:creator>
                    <dcterms:subject xml:lang="en" scheme="keywords" >manual sign communication</dcterms:subject>
                    <dcterms:subject xml:lang="en" scheme="keywords" >mastering spoken languages</dcterms:subject>
                    <dcterms:subject xml:lang="en" scheme="keywords" >mastering full sign languages</dcterms:subject>
                    <dcterms:subject xml:lang="en" scheme="keywords" >intellectual disabilities</dcterms:subject>
                    <dcterms:subject xml:lang="en" scheme="keywords" >cerebral palsy</dcterms:subject>
                    <dcterms:subject xml:lang="en" scheme="keywords" >autism</dcterms:subject>
                    <dcterms:subject xml:lang="en" scheme="keywords" >aphasia</dcterms:subject>
                    <dcterms:subject scheme="ISI" >Linguistics</dcterms:subject>
                    <dcterms:subject scheme="BISAC" >LAN000000</dcterms:subject>
                    <dcterms:abstract xml:lang="en" >Simplified Signs presents a system of manual sign communication intended for special populations who have had limited success mastering spoken or full sign languages. It is the culmination of over twenty years of research and development by the authors. The Simplified Sign System has been developed and tested for ease of sign comprehension, memorization, and formation by limiting the complexity of the motor skills required to form each sign, and by ensuring that each sign visually resembles the meaning it conveys. Volume 1 outlines the research underpinning and informing the project, and places the Simplified Sign System in a wider context of sign usage, historically and by different populations. Volume 2 presents the lexicon of signs, totaling approximately 1000 signs, each with a clear illustration and a written description of how the sign is formed, as well as a memory aid that connects the sign visually to the meaning that it conveys. While the Simplified Sign System originally was developed to meet the needs of persons with intellectual disabilities, cerebral palsy, autism, or aphasia, it may also assist the communication needs of a wider audience - such as healthcare professionals, aid workers, military personnel, travellers or parents, and children who have not yet mastered spoken language. The system also has been shown to enhance learning for individuals studying a foreign language. Lucid and comprehensive, this work constitutes a valuable resource that will enhance the communicative interactions of many different people, and will be of great interest to researchers and educators alike. As with all Open Book publications, this entire book is available to read for free on the publisher’s website. Printed and digital editions, together with supplementary digital material, can also be found at www.openbookpublishers.com</dcterms:abstract>
                    <dcterms:identifier scheme="URN" >urn:isbn:978-1-78374-923-2</dcterms:identifier>
                    <dcterms:identifier scheme="URN" >urn:eisbn:979-10-365-6305-8</dcterms:identifier>
                </mets:xmlData>
            </mets:mdWrap>
        </mets:dmdSec> 
"""

    def test_simple_extraction(self):
        """Test simple tags without attributes."""
        extractor = XMLExtractor(self.simple_xml)

        result = extractor.extract_content("title")
        expected = [XMLData(content="Learn Python", attributes={})]
        self.assertEqual(result, expected)

        result = extractor.extract_content("author")
        expected = [XMLData(content="John Doe", attributes={})]
        self.assertEqual(result, expected)

    def test_extraction_with_attributes(self):
        """Test tags with attributes."""
        extractor = XMLExtractor(self.complex_xml)

        result = extractor.extract_content("book")
        expected = [
            XMLData(
                content="<title>Learn Python</title>\n                <author>John Doe</author>",
                attributes={"id": "1", "genre": "tech"},
            ),
            XMLData(
                content="<title>Introduction to XML</title>\n                <author>Marie Curie</author>",
                attributes={"id": "2", "genre": "tech"},
            ),
        ]
        result.sort()
        expected.sort()
        self.assertListEqual(result, expected)

        # Extraction in child node
        sub_extractor = XMLExtractor(result[0].content)

        result = sub_extractor.extract_content("title")
        expected = [XMLData(content="Introduction to XML", attributes={})]
        self.assertEqual(result, expected)

        result = extractor.extract_content("note")
        expected = [
            XMLData(
                content="This is a sample document.", attributes={"importance": "high"}
            )
        ]
        self.assertEqual(result, expected)

    def test_empty_tags(self):
        """Test tags with empty content."""
        extractor = XMLExtractor(self.empty_content_xml)

        result = extractor.extract_content("title")
        expected = [XMLData(content="", attributes={})]
        self.assertEqual(result, expected)

        result = extractor.extract_content("author")
        expected = [XMLData(content="", attributes={})]
        self.assertEqual(result, expected)

    def test_no_matching_tags(self):
        """Test when no matching tags are found."""
        extractor = XMLExtractor(self.no_matching_tag_xml)

        result = extractor.extract_content("title")
        expected = []
        self.assertEqual(result, expected)

        result = extractor.extract_content("author")
        expected = []
        self.assertEqual(result, expected)

    def test_nonexistent_tags(self):
        """Test when the tag does not exist in the XML."""
        extractor = XMLExtractor(self.simple_xml)

        result = extractor.extract_content("chapter")
        expected = []
        self.assertEqual(result, expected)

    def test_invalid_input(self):
        """Test invalid input type."""
        with self.assertRaises(ValueError):
            XMLExtractor(123)  # type: ignore

    def test_extract_content_attribute_filter(self):
        """
        Test extract_content_attribute_filter method.
        """
        extractor = XMLExtractor(self.xml_mets)
        result = extractor.extract_content_attribute_filter(
            "dcterms:identifier", "scheme", "URI"
        )
        expected = [
            XMLData(
                content="https://books.openedition.org/obp/14432",
                attributes={"scheme": "URI"},
            )
        ]
        self.assertEqual(result, expected)
