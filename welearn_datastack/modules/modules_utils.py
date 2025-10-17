from typing import Any, Dict, List

from welearn_database.data.models import WeLearnDocument


def to_dict_url_trace(
    obj_list: List[WeLearnDocument],
    url_attribute_name: str = "url",
    trace_attribute_name: str = "trace",
) -> Dict[str, Any]:
    """
    Convert a list of object to a dict with url as key and trace as value
    :param obj_list: List of object
    :param url_attribute_name: Name of the attribute containing the url
    :param trace_attribute_name: Name of the attribute containing the trace
    :return: Dict with url as key and trace as value
    """
    return {
        getattr(obj, url_attribute_name): getattr(obj, trace_attribute_name)
        for obj in obj_list
    }
