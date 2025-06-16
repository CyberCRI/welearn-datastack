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
    "de": 179,
    "es": 218,
    "fr": 195,
    "jp": 193,
    "pt": 181,
    "ar": 138,
    "it": 188,
    "nl": 202,
    "zh": 158,
}

FLESCH_KINCAID_CONSTANTS = {
    "en": {
        "fre_base": 206.835,
        "fre_sentence_length": 1.015,
        "fre_syll_per_word": 84.6,
    },
    "de": {
        "fre_base": 180,
        "fre_sentence_length": 1,
        "fre_syll_per_word": 58.5,
    },
    "es": {
        "fre_base": 206.84,
        "fre_sentence_length": 1.02,
        "fre_syll_per_word": 60.0,
    },
    "fr": {
        "fre_base": 207,
        "fre_sentence_length": 1.015,
        "fre_syll_per_word": 73.6,
    },
    "it": {
        "fre_base": 217,
        "fre_sentence_length": 1.3,
        "fre_syll_per_word": 60.0,
    },
    "nl": {
        "fre_base": 206.835,
        "fre_sentence_length": 0.93,
        "fre_syll_per_word": 77,
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

# Open Alex code publishers we don't want to retrieve (According to https://www.predatoryjournals.org/the-list/publishers)
# In this order :
# Canadian Center of Science and Education, Academic Journals, Lectito Journals, Pulsus Group, Business Perspectives,
# Econjournals, Frontiers, Multidisciplinary Digital Publishing Institute (MDPI), WIT Press, Qingres, NobleResearch,
# TSNS “Interaktiv plus”, LLC, Science and Education Centre of North America, Medical science, AEPress,
# Scientific Journals, Atlas Publishing, LP, Baishideng Publishing Group, National Association of Scholars,
# Allied Academies, Smart Science & Technology, Lupine Publishers, Ivy Union Publishing, PiscoMed Publishing,
# Scientia Socialis, Scientia Socialis, SciPress Ltd, Australian International Academic Centre Pty. Ltd., Eurasian Publications,
# Access Journals, Open Access Journals, Open Access Library, Applied Science Innovations, AgiAl Publishing House,
# Tomas Publishing, Herbert Open Access Journals (Herbert Publications), Publishing Press, World Scientific Publishing,
# Hindawi, Research Publishing Group, Science and Technology Publishing, Lectito, MedCrave, American Journal,
# New Century Science Press, New Science, International Scientific Publications,
# ISPACS (International Scientific Publications and Consulting Services),
# International Foundation for Research and Development, IGI Global, Scientific Research Publishing (SCIRP),
# Sciedu Press, e-Century Publishing Corporation, American Scientific Publishers, SciTechnol, Virtus Interpress,
# Oriental Scientific Publishing Company, Center for Promoting Ideas, Excellent Publishers, IGM Publication, OPAST,
# Medip Academy, Medip Academy, Academic Sciences, Innovare Academic Sciences, Medtext Publications, Globeedu Group,
# Research Journal, Galore Knowledge Publication Pvt. Ltd., Scientific Education, Gupta Publications,
# International Information Institute, Innovative Journals, Asian Research Consortium,
# The International Association for Information, Culture, Human and Industry Technology,
# Sci Forschen, Horizon Research Publishing, Lawarence Press, AI Publications, Kowsar Publishing, Hilaris, Sadguru Publications,
# Institute of Advanced Scientific Research, International Educative Research Foundation And Publisher, Research Publisher,
# Open Access Publishing Group, Advanced Research Publications, Open Science, Society of Education, Elmer Press,
# Macrothink Institute, Universe Scientific Publishing, IJRCM, Auctores Publishing, LLC, Management Journals,
# Scholars Research Library, Academy Journals, International Journals of Multidisciplinary Research Academy,
# Multidisciplinary Journals, Science Publishing Group, WFL Publisher, Open Journal Systems, EnPress Publisher, CARI Journals, Pushpa Publishing House,
# Global Vision Press, RedFame Publishing, i-manager Publications, Infogain Publication,
# International Digital Organization for Scientific Information (IDOSI), Blue Eyes Intelligence Engineering & Sciences Publication,
# Academia Research, Academic Research Publishing Group, Hikari Ltd., Enviro Publishers / Enviro Research Publishers,
# GRDS Publishing, Internet Scientific Publications, JSciMed Central, International Academy of Business, Remedy Publications, TMR Publishing Group
PUBLISHERS_TO_AVOID = [
    "P4310321074",
    "P4310320063",
    "P4310313016",
    "P4310321069",
    "P4310318345",
    "P4310320527",
    "P4310310987",
    "P4310311589",
    "P4310311735",
    "P4310311864",
    "P4310312766",
    "P4310312881",
    "P4310313755",
    "P4310314442",
    "P4310315241",
    "P4310315663",
    "P4310315735",
    "P4310315795",
    "P4310315810",
    "P4310315843",
    "P4310316567",
    "P4310316790",
    "P4310317086",
    "P4310317519",
    "P4310317519",
    "P4310317790",
    "P4310318044",
    "P4310318299",
    "P4310318591",
    "P4310318591",
    "P4310318591",
    "P4310318723",
    "P4310318992",
    "P4310319563",
    "P4310319724",
    "P4310319811",
    "P4310319815",
    "P4310319869",
    "P4310319908",
    "P4310319982",
    "P4310320063",
    "P4310320093",
    "P4310320259",
    "P4310320321",
    "P4310320321",
    "P4310320334",
    "P4310320334",
    "P4310320342",
    "P4310320424",
    "P4310320480",
    "P4310320842",
    "P4310320994",
    "P4310321646",
    "P4310321726",
    "P4310322050",
    "P4320800656",
    "P4320800740",
    "P4322614448",
    "P4322632798",
    "P4322696804",
    "P4322697004",
    "P4322697004",
    "P4322697801",
    "P4322697801",
    "P4322699584",
    "P4322764864",
    "P4322764886",
    "P4323237698",
    "P4323237894",
    "P4323253347",
    "P4323283508",
    "P4323430444",
    "P4323432882",
    "P4323971528",
    "P4323972566",
    "P4324001558",
    "P4324004145",
    "P4324004152",
    "P4324113678",
    "P4324147902",
    "P4324262928",
    "P4324341404",
    "P4327874083",
    "P4327874083",
    "P4327874097",
    "P4327876843",
    "P4327876862",
    "P4327986823",
    "P4328135221",
    "P4328141805",
    "P4353105723",
    "P4353107447",
    "P4353108569",
    "P4353108604",
    "P4360969180",
    "P4360969395",
    "P4360969395",
    "P4360969395",
    "P4360969447",
    "P4361063272",
    "P4361075571",
    "P4361121922",
    "P4362561667",
    "P4362643899",
    "P4362724842",
    "P4362724891",
    "P4362724893",
    "P4363603480",
    "P4364118893",
    "P4364309641",
    "P4365393707",
    "P4366111303",
    "P4366371026",
    "P4376634143",
    "P4383858765",
    "P4404533578",
    "P4404662409",
    "P4404668943",
    "P4404677186",
]
