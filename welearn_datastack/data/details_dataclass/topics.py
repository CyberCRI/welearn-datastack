from dataclasses import dataclass


@dataclass
class TopicDetails:
    external_id: str | None
    name: str
    depth: int
    external_depth_name: str | None
    directly_contained_in: list[str]
