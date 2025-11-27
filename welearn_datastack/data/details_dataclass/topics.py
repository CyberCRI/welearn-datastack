from dataclasses import dataclass


@dataclass
class TopicDetails:
    external_id: str
    name: str
    depth: int
    external_depth_name: str
    directly_contained_in: list[str]
