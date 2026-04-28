from urllib.parse import urlparse

from welearn_datastack.data.enumerations import URLParts


def extract_url_parts(
    url: str, parts_to_extract: list[URLParts], concat: bool
) -> str | list[str]:
    """
    Extract the specified parts of a URL and return them as a concatenated string or a list of strings.
    :param url: The URL to extract parts from
    :param parts_to_extract: A list of URLParts enum values specifying which parts to extract
    :param concat: If True, return the extracted parts as a concatenated string. If False, return the extracted parts as a list of strings.
    :return: The extracted parts as a concatenated string or a list of strings, depending on the value of concat. If no parts are extracted, return an empty list.
    """
    parsed = urlparse(url)
    # Init empty list of 6 elements to store the extracted parts, in the order of URLParts enum
    extracted_parts = ["" for _ in range(6)]

    for part in parts_to_extract:
        match part:
            case URLParts.SCHEME:
                extracted_parts[0] = parsed.scheme
            case URLParts.NETLOC:
                extracted_parts[1] = parsed.netloc
            case URLParts.PATH:
                extracted_parts[2] = parsed.path
            case URLParts.PARAMS:
                extracted_parts[3] = parsed.params
            case URLParts.QUERY:
                extracted_parts[4] = parsed.query
            case URLParts.FRAGMENT:
                extracted_parts[5] = parsed.fragment

    if concat:
        return "".join(extracted_parts)
    else:
        ret = [i for i in extracted_parts if i != ""]
        return ret if len(ret) > 1 else []


def extract_url_parts_post_netloc(url: str, remove_start_slash: bool = True) -> str:
    """
    Extract the path, params, query and fragment parts of a URL and concatenate them into a single string. Optionally remove the starting slash from the path.
    :param url: The URL to extract parts from
    :param remove_start_slash: If True, remove the starting slash from the path part if it exists. Default is True.
    :return: The concatenated string of the path, params, query and fragment parts of the URL, with the starting
        slash removed from the path if remove_start_slash is True and the path starts with a slash.
        If no parts are extracted, return an empty string.
    """
    ret = extract_url_parts(
        url=url,
        parts_to_extract=[
            URLParts.PATH,
            URLParts.PARAMS,
            URLParts.QUERY,
            URLParts.FRAGMENT,
        ],
        concat=True,
    )
    if remove_start_slash and ret.startswith("/"):
        ret = ret[1:]
    return ret


def extract_doi_number(url: str) -> str:
    """
    Extract the DOI number from a URL if it exists. The DOI number is expected to be in the format "10.xxxx/xxxxx".
    :param url: The URL to extract the DOI number from
    :return: The extracted DOI number as a string, or an empty string if no DOI number is found
    """
    path = urlparse(url).path
    if path.startswith("/"):
        ret = path[1:]
    else:
        return ""

    if ret.startswith("10."):
        return ret
    else:
        return ""