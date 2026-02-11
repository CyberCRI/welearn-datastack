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


class WrongFormat(LocalModelsExceptions):
    """
    The format of the item is not accepted
    """

    def __init__(self, msg="The format of the item is not accepted", *args):
        super().__init__(msg, *args)


class WrongLangFormat(WrongFormat):
    """
    Lang must be in ISO-639-1 format and it's not
    """

    def __init__(self, msg="Lang must be in ISO-639-1 format", *args):
        super().__init__(msg, *args)



class InvalidURLScheme(WrongFormat):
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


class LegalException(ManagementExceptions):
    """
    Legal exception, raised when the content is not authorized to be used
    """

    def __init__(self, msg="This content is not authorized to be used", *args):
        super().__init__(msg, *args)


class UnauthorizedLicense(LegalException):
    """
    License is not authorized
    """

    def __init__(self, msg="This license is not authorized", *args):
        super().__init__(msg, *args)


class ClosedAccessContent(LegalException):
    """
    Content is closed access
    """


class NotEnoughData(ManagementExceptions):
    """
    Not enough data to perform this action
    """

    def __init__(self, msg="Not enough data to perform this action", *args):
        super().__init__(msg, *args)


class LanguageCodeError(ManagementExceptions):
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


class NoModelFoundError(LocalModelsExceptions):
    """Raised when there is no model found"""


class ErrorWhileDeletingChunks(Exception):
    """Raised when there is an error while deleting chunks"""


class ErrorWhileInsertingParagraph(Exception):
    """Raised when there is an error while inserting paragraphs"""


class NotBatchFoundError(Exception):
    """Raised when there is no batch found"""


class NoLimitSet(Exception):
    """"""


class TooMuchLanguages(ManagementExceptions):
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


class UnauthorizedPublisher(LegalException):
    """
    Raised when the publisher is not authorized
    """


class UnauthorizedState(LegalException):
    """
    Raised when the state is not authorized
    """


class NoLicenseFoundError(LegalException):
    """
    Raised when there is no license found
    """


class NotExpectedAmountOfItems(Exception):
    """
    Raised when the amount of items in list is not the expected one
    """


class NotExpectedMoreThanOneItem(NotExpectedAmountOfItems):
    """
    Raised when there is more than one item in list but only one is expected
    """


class WrongExternalIdFormat(WrongFormat):
    """
    Raised when the external id format is not correct
    """

    def __init__(self, external_id_name: str, msg: str, *args):
        super().__init__(msg, *args)
        msg = f"The external id {external_id_name} format is not correct"


class NoContent(NotEnoughData):
    """
    No content found in this document
    """

    def __init__(self, msg="No content found in this document", *args):
        super().__init__(msg, *args)
