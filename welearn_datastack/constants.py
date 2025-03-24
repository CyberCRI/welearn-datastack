from welearn_datastack.data.wikipedia_container import WikipediaContainer

WIKIPEDIA_CONTAINERS = [
    WikipediaContainer(
        wikipedia_path="Category:Portail:Développement_durable/Articles_liés",
        depth=1,
        lang="fr",
    ),
    WikipediaContainer(
        wikipedia_path="Category:Portail:Éducation/Articles_liés", depth=1, lang="fr"
    ),  # SDG4
    WikipediaContainer(
        wikipedia_path="Category:Portail:Genre/Articles_liés", depth=1, lang="fr"
    ),  # SDG5
    WikipediaContainer(
        wikipedia_path="Category:Portail:Eau/Articles_liés", depth=1, lang="fr"
    ),  # SDG6
    WikipediaContainer(
        wikipedia_path="Category:Portail:Énergie_renouvelable/Articles_liés",
        depth=1,
        lang="fr",
    ),  # SDG7 & énergie
    WikipediaContainer(
        wikipedia_path="Category:Portail:Énergie/Articles_liés", depth=1, lang="fr"
    ),  # SDG7 & énergie
    WikipediaContainer(
        wikipedia_path="Category:Portail:Industrie/Articles_liés", depth=1, lang="fr"
    ),  # SDG9
    WikipediaContainer(
        wikipedia_path="Category:Portail:Architecture_et_urbanisme/Articles_liés",
        depth=1,
        lang="fr",
    ),  # SDG11
    WikipediaContainer(
        wikipedia_path="Category:Portail:Commerce/Articles_liés", depth=1, lang="fr"
    ),  # SDG12
    WikipediaContainer(
        wikipedia_path="Category:Portail:Climat/Articles_liés", depth=1, lang="fr"
    ),  # SDG13
    WikipediaContainer(
        wikipedia_path="Category:Portail:Mer/Articles_liés", depth=1, lang="fr"
    ),  # SDG14
    WikipediaContainer(
        wikipedia_path="Category:Portail:Maritime/Articles_liés", depth=1, lang="fr"
    ),  # SDG14
    WikipediaContainer(
        wikipedia_path="Category:Portail:Pêche/Articles_liés", depth=1, lang="fr"
    ),  # SDG14
    WikipediaContainer(
        wikipedia_path="Category:Portail:Conservation_de_la_nature/Articles_liés",
        depth=1,
        lang="fr",
    ),  # SDG15 & biodiversité
    WikipediaContainer(
        wikipedia_path="Category:Portail:Bois_et_forêt/Articles_liés",
        depth=1,
        lang="fr",
    ),  # SDG15
    WikipediaContainer(
        wikipedia_path="Category:Portail:Montagne/Articles_liés", depth=1, lang="fr"
    ),  # SDG15
    WikipediaContainer(
        wikipedia_path="Category:Portail:Paix/Articles_liés", depth=1, lang="fr"
    ),  # SDG16
    WikipediaContainer(
        wikipedia_path="Category:Portail:Droit/Articles_liés", depth=1, lang="fr"
    ),  # SDG16
    WikipediaContainer(
        wikipedia_path="Category:Portail:Humanitaire_et_développement/Articles_liés",
        depth=1,
        lang="fr",
    ),  # SDG17
    WikipediaContainer(
        wikipedia_path="Category:Portail:Relations_internationales/Articles_liés",
        depth=1,
        lang="fr",
    ),  # SDG17
    WikipediaContainer(
        wikipedia_path="Category:Portail:Écologie/Articles_liés", depth=1, lang="fr"
    ),  # écologie scientifique
    WikipediaContainer(
        wikipedia_path="Category:Portail:Écologie_politique/Articles_liés",
        depth=1,
        lang="fr",
    ),  # écologie politique
    WikipediaContainer(
        wikipedia_path="Category:Portail:Écologisme/Articles_liés", depth=1, lang="fr"
    ),  # écologisme
    WikipediaContainer(
        wikipedia_path="Category:Portail:Environnement/Articles_liés",
        depth=1,
        lang="fr",
    ),  # environnement
    WikipediaContainer(
        wikipedia_path="Category:Portail:Réchauffement_climatique/Articles_liés",
        depth=1,
        lang="fr",
    ),
    WikipediaContainer(wikipedia_path="Category:Climate_change", depth=2, lang="en"),
    WikipediaContainer(wikipedia_path="Category:Renewable energy", depth=2, lang="en"),
    WikipediaContainer(
        wikipedia_path="Category:Natural_environment", depth=1, lang="en"
    ),
    WikipediaContainer(wikipedia_path="Category:Ecology", depth=2, lang="en"),
    WikipediaContainer(wikipedia_path="Category:Feminism", depth=2, lang="en"),
    WikipediaContainer(
        wikipedia_path="Category:Sustainable_development", depth=2, lang="en"
    ),
]

TED_API_URL = "https://zenith-prod-alt.ted.com/api/search"

TED_URL = "https://www.ted.com/talks/"

HAL_SEARCH_URL = "https://api.archives-ouvertes.fr/search/"

DICT_READING_SPEEDS_LANG = {
    "en": 228,
    "fr": 195,
}

FLESCH_KINCAID_CONSTANTS = {
    "en": {
        "fre_base": 206.835,
        "fre_sentence_length": 1.015,
        "fre_syll_per_word": 84.6,
    },
    "fr": {
        "fre_base": 207,
        "fre_sentence_length": 1.015,
        "fre_syll_per_word": 73.6,
    },
}

ANTI_URL_REGEX = r"\(?((www)|((https?|ftp|file):\/\/))[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]\)?"

CREATIVE_COMMONS_BASE_URL = "creativecommons.org"

HTTP_CREATIVE_COMMONS = f"http://{CREATIVE_COMMONS_BASE_URL}"
HTTPS_CREATIVE_COMMONS = f"https://{CREATIVE_COMMONS_BASE_URL}"

AUTHORIZED_LICENSES = [
    f"{HTTP_CREATIVE_COMMONS}/licenses/by/3.0/",  # Damn non IT people
    f"{HTTP_CREATIVE_COMMONS}/licenses/by/4.0/",
    f"{HTTP_CREATIVE_COMMONS}/licenses/by-sa/4.0/",
    f"{HTTP_CREATIVE_COMMONS}/licenses/by-sa/3.0/",
    f"{HTTP_CREATIVE_COMMONS}/publicdomain/zero/1.0/",
    f"{HTTP_CREATIVE_COMMONS}/publicdomain/mark/1.0/",
    f"{HTTPS_CREATIVE_COMMONS}/licenses/by/3.0/",  # At least article #1 is in this license version
    f"{HTTPS_CREATIVE_COMMONS}/licenses/by/4.0/",
    f"{HTTPS_CREATIVE_COMMONS}/publicdomain/zero/1.0/",
    f"{HTTPS_CREATIVE_COMMONS}/publicdomain/mark/1.0/",
    f"{HTTPS_CREATIVE_COMMONS}/licenses/by-sa/4.0/",
    f"{HTTPS_CREATIVE_COMMONS}/licenses/by-sa/3.0/",
]
HEADERS = {
    "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "TE": "Trailers",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/136.0",
}

MD_OE_BOOKS_BASE_URL = "https://oai.openedition.org/?verb=GetRecord&identifier=oai:books.openedition.org:<md_id>&metadataPrefix=mets"

HAL_URL_BASE = "https://hal.science/"

OPEN_ALEX_BASE_URL = "https://api.openalex.org/works"

YEAR_FIRST_DATE_FORMAT = "%Y-%m-%d"

WIKIPEDIA_BASE_URL = "https://<lang>.wikipedia.org/"
