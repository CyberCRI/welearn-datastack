from dataclasses import dataclass


@dataclass
class XMLData:
    content: str
    attributes: dict

    def __ge__(self, other):
        return self.content >= other.content

    def __gt__(self, other):
        return self.content > other.content

    def __le__(self, other):
        return self.content <= other.content

    def __lt__(self, other):
        return self.content < other.content

    def __eq__(self, other):
        return self.content == other.content

    def __str__(self):
        return str({"content": self.content, "attributes": self.attributes})
