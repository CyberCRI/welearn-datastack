import dataclasses
from typing import Dict, List, Tuple

from pypdf import PdfReader

from welearn_datastack.exceptions import NotEnoughData


class PDFBodyInfo:
    """
    A class used to represent the body information of a PDF document.

    Attributes
    ----------
    heights : Dict[float, int]
        a dictionary that maps the height of a character to its frequency in the document
    margin_x : Dict[float, int]
        a dictionary that maps the x position of a character to its frequency in the document
    height_y_min_max_per_page : List[Dict[float, Tuple[float, float]]]
        a list of dictionaries, each representing a page in the document. Each dictionary maps the height of a character to a tuple of its minimum and maximum y positions on the page
    """

    def __init__(self, pdf_reader: PdfReader):
        heights: Dict[float, int] = {}
        x_pos: Dict[float, int] = {}
        height_y_min_max_per_page: List[Dict[float, Tuple[float, float]]] = []

        number_of_pages = len(pdf_reader.pages)

        for i in range(number_of_pages):
            page_y_min_max_heights: Dict[float, Tuple[float, float]] = {}
            height_y_min_max_per_page.append({})

            def get_characters_heights(text, cm, tm, font_dict, font_size):
                """
                Helper method used by visitor text to get the height of characters in a page

                Parameters
                ----------
                text : str
                    the text of the character
                cm : List[float]
                    the character matrix
                tm : List[float]
                    the text matrix
                font_dict : Dict
                    the font dictionary
                font_size : float
                    the font size
                """
                char_height = round(font_size, 0)
                x = round(max([cm[4], tm[4]]), 0)
                y = round(max([cm[5], tm[5]]), 0)
                if text.strip():
                    if char_height not in heights:
                        heights[char_height] = 0
                    if x not in x_pos:
                        x_pos[x] = 0
                    if char_height not in page_y_min_max_heights:
                        page_y_min_max_heights[char_height] = (y, y)

                    heights[char_height] += 1
                    x_pos[x] += 1
                    if y < page_y_min_max_heights[char_height][0]:
                        page_y_min_max_heights[char_height] = (
                            y,
                            page_y_min_max_heights[char_height][1],
                        )
                    if y > page_y_min_max_heights[char_height][1]:
                        page_y_min_max_heights[char_height] = (
                            page_y_min_max_heights[char_height][0],
                            y,
                        )
                height_y_min_max_per_page[i].update(page_y_min_max_heights)

            page = pdf_reader.pages[i]
            page.extract_text(
                orientations=0,
                visitor_text=get_characters_heights,
            )
        self.heights = heights
        self.margin_x = x_pos
        self.height_y_min_max_per_page = height_y_min_max_per_page

    @property
    def file_size(self):
        return sum(self.heights.values())

    @property
    def body_range(self):
        # Try to catch at least 60% of document
        body_height = max(self.heights, key=self.heights.get)
        qty_already_catched = self.heights[body_height]
        ret_range = [body_height]

        # There is 10 attempts to catch more 60% of document, if not possible, raise exception
        raise_exception = True
        for i in range(1, 10):
            if qty_already_catched / sum(self.heights.values()) > 0.6:
                raise_exception = False
                break
            upper = body_height + i
            lower = body_height - i
            if upper in self.heights:
                ret_range.append(upper)
                qty_already_catched += self.heights[upper]
            if lower in self.heights:
                ret_range.append(lower)
                qty_already_catched += self.heights[lower]
        if raise_exception:
            raise NotEnoughData("Could not catch 60% of document")
        return ret_range

    @property
    def most_used_x(self):
        return max(self.margin_x, key=self.margin_x.get)

    def margin_top_y(self, page_number: int):
        """
        Get the higher y used by body in a page
        :param page_number: page number
        :return: higher y used by body
        """
        page = self.height_y_min_max_per_page[page_number]
        body_highers_ys = [0.0]
        selected_size = 0
        for v in self.body_range:
            if v in page:
                body_highers_ys.append(page[v][1])
                selected_size = v
        return max(body_highers_ys) + selected_size

    def margin_bottom_y(self, page_number: int):
        """
        Get the lower y used by body in a page
        :param page_number: page number
        :return: lower y used by body
        """
        page = self.height_y_min_max_per_page[page_number]
        body_lowest_ys = []
        selected_size = 0
        for v in self.body_range:
            if v in page:
                body_lowest_ys.append(page[v][0])
                selected_size = v

        if not body_lowest_ys:
            return 0.0
        return min(body_lowest_ys) - selected_size
