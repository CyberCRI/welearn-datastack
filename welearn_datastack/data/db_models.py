from datetime import datetime
from enum import StrEnum, auto  # type: ignore
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, LargeBinary, UniqueConstraint, func, types
from sqlalchemy.dialects.postgresql import ENUM, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from welearn_datastack.data.enumerations import Counter, Step
from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

load_dotenv_local()


class DbSchemaEnum(StrEnum):
    CORPUS_RELATED = auto()
    DOCUMENT_RELATED = auto()
    USER_RELATED = auto()


class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: types.JSON,
        datetime: TIMESTAMP(timezone=False),
        float: types.NUMERIC,
    }


class Corpus(Base):
    __tablename__ = "corpus"
    __table_args__ = {"schema": DbSchemaEnum.CORPUS_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    source_name: Mapped[str]
    is_fix: Mapped[bool]
    binary_treshold: Mapped[float] = mapped_column(nullable=False, default=0.5)
    is_active: Mapped[bool]
    category_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.category.id"),
    )


class Category(Base):
    __tablename__ = "category"
    __table_args__ = {"schema": DbSchemaEnum.CORPUS_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    title: Mapped[str]


class WeLearnDocument(Base):
    __tablename__ = "welearn_document"
    __table_args__ = (
        UniqueConstraint("url", name="welearn_document_url_key"),
        {"schema": DbSchemaEnum.DOCUMENT_RELATED.value},
    )

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    external_id: Mapped[str | None]
    url: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str | None]
    lang: Mapped[str | None]
    description: Mapped[str | None]
    full_content: Mapped[str | None]
    details: Mapped[dict[str, Any] | None]
    trace: Mapped[int | None] = mapped_column(types.BIGINT)
    corpus_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.corpus.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )

    corpus: Mapped["Corpus"] = relationship("Corpus")
    # process_states: Mapped[List["ProcessState"]] = relationship(
    #     back_populates="WeLearnDocument"
    # )


class ProcessState(Base):
    __tablename__ = "process_state"
    __table_args__ = {"schema": DbSchemaEnum.DOCUMENT_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        ENUM(*(e.value.lower() for e in Step), name="step", schema="document_related"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    operation_order = mapped_column(
        types.BIGINT,
        server_default="nextval('document_related.process_state_operation_order_seq'",
        nullable=False,
    )
    document: Mapped["WeLearnDocument"] = relationship()


class Keyword(Base):
    __tablename__ = "keyword"
    __table_args__ = (
        UniqueConstraint("keyword", name="keyword_unique"),
        {"schema": DbSchemaEnum.DOCUMENT_RELATED.value},
    )

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    keyword: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )


class WeLearnDocumentKeyword(Base):
    __tablename__ = "welearn_document_keyword"
    __table_args__ = (
        UniqueConstraint(
            "welearn_document_id",
            "keyword_id",
            name="unique_welearn_document_keyword_association",
        ),
        {"schema": DbSchemaEnum.DOCUMENT_RELATED.value},
    )
    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    welearn_document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    keyword_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.DOCUMENT_RELATED.value}.keyword.id"),
        nullable=False,
    )


class ErrorRetrieval(Base):
    __tablename__ = "error_retrieval"
    __table_args__ = ({"schema": DbSchemaEnum.DOCUMENT_RELATED.value},)

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )

    document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    http_error_code: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )
    error_info: Mapped[str]

    document: Mapped["WeLearnDocument"] = relationship()


class DocumentSlice(Base):
    __tablename__ = "document_slice"
    __table_args__ = {"schema": DbSchemaEnum.DOCUMENT_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    body: Mapped[str | None]
    order_sequence: Mapped[int]
    embedding_model_name: Mapped[str]

    embedding_model_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.embedding_model.id"),
        nullable=False,
    )

    document: Mapped["WeLearnDocument"] = relationship()
    embedding_model: Mapped["EmbeddingModel"] = relationship()


class EmbeddingModel(Base):
    __tablename__ = "embedding_model"
    __table_args__ = {"schema": DbSchemaEnum.CORPUS_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    title: Mapped[str]
    lang: Mapped[str]


class BiClassifierModel(Base):
    __tablename__ = "bi_classifier_model"
    __table_args__ = {"schema": DbSchemaEnum.CORPUS_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    title: Mapped[str]
    binary_treshold: Mapped[float] = mapped_column(default=0.5)
    lang: Mapped[str]
    used_since: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )


class NClassifierModel(Base):
    __tablename__ = "n_classifier_model"
    __table_args__ = {"schema": DbSchemaEnum.CORPUS_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    title: Mapped[str]
    lang: Mapped[str]
    treshold_sdg_1: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_2: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_3: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_4: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_5: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_6: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_7: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_8: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_9: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_10: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_11: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_12: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_13: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_14: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_15: Mapped[float] = mapped_column(default=0.5)
    treshold_sdg_16: Mapped[float] = mapped_column(default=0.5)
    used_since: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )


class AnalyticCounter(Base):
    __tablename__ = "analytic_counter"
    __table_args__ = {
        "schema": DbSchemaEnum.DOCUMENT_RELATED.value,
    }

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    counter_name: Mapped[Counter]
    counter_value: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )
    document: Mapped["WeLearnDocument"] = relationship()


class CorpusEmbeddingModel(Base):
    __tablename__ = "corpus_embedding_model"
    __table_args__ = (
        UniqueConstraint(
            "corpus_id",
            "embedding_model_id",
            name="unique_corpus_embedding_association",
        ),
        {"schema": DbSchemaEnum.CORPUS_RELATED.value},
    )

    corpus_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.corpus.id"),
        primary_key=True,
    )
    embedding_model_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.embedding_model.id"),
        primary_key=True,
    )

    used_since: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )

    embedding_model: Mapped["EmbeddingModel"] = relationship()
    corpus: Mapped["Corpus"] = relationship()


class CorpusNClassifierModel(Base):
    __tablename__ = "corpus_n_classifier_model"
    __table_args__ = (
        UniqueConstraint(
            "corpus_id",
            "n_classifier_model_id",
            name="unique_corpus_n_classifier_association",
        ),
        {"schema": DbSchemaEnum.CORPUS_RELATED.value},
    )

    corpus_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.corpus.id"),
        primary_key=True,
    )
    n_classifier_model_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.n_classifier_model.id"),
        primary_key=True,
    )

    used_since: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )

    n_classifier_model: Mapped["NClassifierModel"] = relationship()
    corpus: Mapped["Corpus"] = relationship()


class CorpusBiClassifierModel(Base):
    __tablename__ = "corpus_bi_classifier_model"
    __table_args__ = (
        UniqueConstraint(
            "corpus_id",
            "bi_classifier_model_id",
            name="unique_corpus_bi_classifier_association",
        ),
        {"schema": DbSchemaEnum.CORPUS_RELATED.value},
    )

    corpus_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.corpus.id"),
        primary_key=True,
    )
    bi_classifier_model_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.bi_classifier_model.id"),
        primary_key=True,
    )
    used_since: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )

    bi_classifier_model: Mapped["BiClassifierModel"] = relationship()
    corpus: Mapped["Corpus"] = relationship()


class Sdg(Base):
    __tablename__ = "sdg"
    __table_args__ = {"schema": DbSchemaEnum.DOCUMENT_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid,
        primary_key=True,
        nullable=False,
        server_default="gen_random_uuid()",
    )
    slice_id = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.document_slice.id",
            name="sdg_slice_id_fkey2",
        ),
        nullable=False,
    )
    sdg_number: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )

    bi_classifier_model_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.bi_classifier_model.id"),
    )
    n_classifier_model_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.CORPUS_RELATED.value}.n_classifier_model.id"),
    )
    bi_classifier_model: Mapped["BiClassifierModel"] = relationship()
    n_classifier_model: Mapped["NClassifierModel"] = relationship()
    slice: Mapped["DocumentSlice"] = relationship()


class UserProfile(Base):
    __tablename__ = "user_profile"
    __table_args__ = {"schema": DbSchemaEnum.USER_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    username: Mapped[str]
    email: Mapped[str]
    password_digest: Mapped[bytes]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )


class Bookmark(Base):
    __tablename__ = "bookmark"
    __table_args__ = {"schema": DbSchemaEnum.USER_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    user_id = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.USER_RELATED.value}.user_profile.id",
            name="bookmark_user_id_fkey2",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )
    user: Mapped["UserProfile"] = relationship()
    welearn_document: Mapped["WeLearnDocument"] = relationship()


class ChatMessage(Base):
    __tablename__ = "chat_message"
    __table_args__ = {"schema": DbSchemaEnum.USER_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    user_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.USER_RELATED.value}.user_profile.id"),
        nullable=False,
    )
    textual_content: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )
    user: Mapped["UserProfile"] = relationship()


class ReturnedDocument(Base):
    __tablename__ = "returned_document"
    __table_args__ = {"schema": DbSchemaEnum.USER_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    message_id = mapped_column(
        types.Uuid,
        ForeignKey(f"{DbSchemaEnum.USER_RELATED.value}.chat_message.id"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey(
            f"{DbSchemaEnum.DOCUMENT_RELATED.value}.welearn_document.id",
            name="state_document_id_fkey",
        ),
        nullable=False,
    )
    welearn_document: Mapped["WeLearnDocument"] = relationship()
    chat_message: Mapped["ChatMessage"] = relationship()


class APIKeyManagement(Base):
    __tablename__ = "api_key_management"
    __table_args__ = {"schema": DbSchemaEnum.USER_RELATED.value}

    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    title: Mapped[str | None]
    register_email: Mapped[str]
    digest: Mapped[bytes]
    is_active: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
        onupdate=func.localtimestamp(),
    )


class Session(Base):
    __tablename__ = "session"
    __table_args__ = {"schema": "user_related"}
    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    inferred_user_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey("user_related.inferred_user.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    end_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), nullable=False)
    host: Mapped[str | None]
    user = relationship("InferredUser", foreign_keys=[inferred_user_id])


class InferredUser(Base):
    __tablename__ = "inferred_user"
    __table_args__ = {"schema": "user_related"}
    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )


class EndpointRequest(Base):
    __tablename__ = "endpoint_request"
    __table_args__ = {"schema": "user_related"}
    id: Mapped[UUID] = mapped_column(
        types.Uuid, primary_key=True, nullable=False, server_default="gen_random_uuid()"
    )
    session_id: Mapped[UUID] = mapped_column(
        types.Uuid,
        ForeignKey("user_related.session.id"),
        nullable=False,
    )
    endpoint_name: Mapped[str]
    http_code: Mapped[int]
    message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
        default=func.localtimestamp(),
        server_default="NOW()",
    )
    session = relationship("Session", foreign_keys=[session_id])
