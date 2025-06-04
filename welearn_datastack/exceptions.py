class LocalModelsExceptions(Exception):
    """
    Exceptions about models declared in local_models file
    """

    pass


class ManagementExceptions(Exception):
    """
    Exceptions about data management
    """

    pass


class WrongLangFormat(LocalModelsExceptions):
    """
    Lang must be in ISO-639-1 format and it's not
    """

    def __init__(self, msg="Lang must be in ISO-639-1 format", *args):
        super().__init__(msg, *args)


class NoContent(LocalModelsExceptions):
    """
    No content found in this document
    """

    def __init__(self, msg="No content found in this document", *args):
        super().__init__(msg, *args)


class InvalidURLScheme(LocalModelsExceptions):
    """
    Scheme detected in URL is not accepted
    """

    def __init__(self, msg="URL schema is not accepted", *args):
        super().__init__(msg, *args)


class UnknownURL(ManagementExceptions):
    """
    Try to filter on an unknown URL
    """

    def __init__(self, msg="This URL is unknown :", *args):
        super().__init__(msg, *args)


class PluginNotFoundError(ManagementExceptions):
    """
    Plugin not found
    """

    def __init__(self, msg="This corpus is unknown :", *args):
        super().__init__(msg, *args)


class InvalidPluginType(ManagementExceptions):
    """
    Plugin type is not accepted
    """

    def __init__(
        self,
        msg="This plugin type is not accepted, always inherit from interface",
        *args,
    ):
        super().__init__(msg, *args)


class UnauthorizedLicense(Exception):
    """
    License is not authorized
    """

    def __init__(self, msg="This license is not authorized", *args):
        super().__init__(msg, *args)


class ClosedAccessContent(Exception):
    """
    Content is closed access
    """


class NotEnoughData(ManagementExceptions):
    """
    Not enough data to perform this action
    """

    def __init__(self, msg="Not enough data to perform this action", *args):
        super().__init__(msg, *args)


class LanguageCodeError(BaseException):
    """Raised when an invalid language code is used"""

    def __init__(self, message="Invalid language code, must be lower ISO-639-1 code"):
        self.message = message
        super().__init__(self.message)


class VersionNumberError(BaseException):
    """Raised when an invalid version number is used"""

    def __init__(self, message="Invalid version number, must be an integer"):
        self.message = message
        super().__init__(self.message)


class NoPreviousCollectionError(BaseException):
    """Raised when there is no previous collection"""

    def __init__(self, message="No previous collection found"):
        self.message = message
        super().__init__(self.message)


class NoConnectedCollectionError(BaseException):
    """Raised when there is no connected collection"""

    def __init__(self, message="No connected collection found"):
        self.message = message
        super().__init__(self.message)


class NoModelFoundError(Exception):
    """Raised when there is no model found"""


class ErrorWhileDeletingChunks(Exception):
    """Raised when there is an error while deleting chunks"""


class ErrorWhileInsertingParagraph(Exception):
    """Raised when there is an error while inserting paragraphs"""


class NotBatchFoundError(Exception):
    """Raised when there is no batch found"""


class NoLimitSet(Exception):
    """"""


class TooMuchLanguages(Exception):
    """Raised when there is too much languages"""


class NoCorpusFoundInDb(Exception):
    """Raise when there is no corpus found in database"""


class NoDescriptionFoundError(Exception):
    """Raised when there is no description found"""


class PDFPagesSizeExceedLimit(Exception):
    """
    Raised when the PDF pages are too big
    """


class PDFFileSizeExceedLimit(Exception):
    """
    Raise when the PDF full file is too big
    """


class UnauthorizedPublisher(Exception):
    """
    Raised when the publisher is not authorized
    """
