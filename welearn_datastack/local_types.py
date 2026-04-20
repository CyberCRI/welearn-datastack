from typing import Tuple, TypeAlias
from uuid import UUID

# Type aliases

# Tuple with document ID, document title and document size
QuerySizeLimitDocument: TypeAlias = Tuple[UUID, str, int]

# Tuple with document ID, document title, document size and slice size
QuerySizeLimitSlice: TypeAlias = Tuple[UUID, str, int, int]
