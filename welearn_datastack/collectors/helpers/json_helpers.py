from typing import List


def search_url_field(data: dict | List, url_field: str) -> List[str]:
    ret = []

    match data:
        case dict():
            if url_field in data:
                ret.append(data[url_field])
            else:
                for k, v in data.items():
                    ret += search_url_field(v, url_field)
        case list():
            for v in data:
                ret += search_url_field(v, url_field)
    return ret
