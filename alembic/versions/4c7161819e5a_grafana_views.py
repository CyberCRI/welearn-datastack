"""grafana_views

Revision ID: 4c7161819e5a
Revises: 5d82613c9aca
Create Date: 2025-10-08 13:55:36.123188

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c7161819e5a"
down_revision: Union[str, None] = "5d82613c9aca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
    CREATE OR REPLACE VIEW grafana.corpus
    AS SELECT corpus.id,
    corpus.source_name,
    corpus.is_fix,
    corpus.binary_treshold
   FROM corpus_related.corpus;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.document_state_summary
AS SELECT corpus.source_name,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'url_retrieved'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS url_retrieved_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'document_scraped'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS document_scraped_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'document_is_irretrievable'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS document_is_irretrievable_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'document_vectorized'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS document_vectorized_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'document_classified_sdg'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS document_classified_sdg_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'document_classified_non_sdg'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS document_classified_non_sdg_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'document_in_qdrant'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS document_in_qdrant_count,
    count(DISTINCT
        CASE
            WHEN process_state.title = 'kept_for_trace'::document_related.step THEN process_state.document_id
            ELSE NULL::uuid
        END) AS kept_for_trace_count,
    count(DISTINCT
        CASE
            WHEN process_state.title IS NULL THEN welearn_document.id
            ELSE NULL::uuid
        END) AS no_state_count,
    count(DISTINCT welearn_document.id) AS total_documents
   FROM corpus_related.corpus
     LEFT JOIN document_related.welearn_document ON corpus.id = welearn_document.corpus_id
     LEFT JOIN document_related.process_state ON welearn_document.id = process_state.document_id
  GROUP BY corpus.source_name;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.endpoint_request
AS SELECT endpoint_request.id,
    endpoint_request.session_id,
    endpoint_request.endpoint_name,
    endpoint_request.http_code,
    endpoint_request.message,
    endpoint_request.created_at
   FROM user_related.endpoint_request;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.inferred_user
AS SELECT inferred_user.id,
    inferred_user.created_at
   FROM user_related.inferred_user;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.process_state
AS SELECT process_state.id,
    process_state.document_id,
    process_state.title,
    process_state.created_at,
    process_state.operation_order
   FROM document_related.process_state;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.qty_endpoints_per_user
AS SELECT iu.*::user_related.inferred_user AS iu,
    count(1) AS count
   FROM user_related.endpoint_request er
     JOIN user_related.session s ON s.id = er.session_id
     JOIN user_related.inferred_user iu ON iu.id = s.inferred_user_id
  GROUP BY iu.id;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.qty_session_endpoint_per_user
AS SELECT s.inferred_user_id,
    s.host,
    count(DISTINCT s.id) AS count_sessions,
    count(er.id) AS count_endpoints
   FROM user_related.session s
     LEFT JOIN user_related.endpoint_request er ON s.id = er.session_id
  GROUP BY s.inferred_user_id, s.host;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.qty_session_user_per_host
AS SELECT s.host,
    count(1) AS count_sessions,
    count(DISTINCT s.inferred_user_id) AS count_users
   FROM user_related.session s
  GROUP BY s.host;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana."session"
AS SELECT session.id,
    session.inferred_user_id,
    session.created_at,
    session.end_at,
    session.host
   FROM user_related.session;
    """
    )
    op.execute(
        """
CREATE OR REPLACE VIEW grafana.document_latest_state
AS SELECT DISTINCT ON (ps.document_id) ps.id,
    ps.document_id,
    wd.corpus_id,
    wd.lang,
    ps.title,
    ps.created_at,
    ps.operation_order
   FROM document_related.process_state ps
     JOIN document_related.welearn_document wd ON ps.document_id = wd.id
  ORDER BY ps.document_id, ps.operation_order DESC;
    """
    )


def downgrade():
    op.execute("DROP VIEW IF EXISTS grafana.document_latest_state;")
    op.execute("DROP VIEW IF EXISTS grafana.session;")
    op.execute("DROP VIEW IF EXISTS grafana.qty_session_user_per_host;")
    op.execute("DROP VIEW IF EXISTS grafana.qty_session_endpoint_per_user;")
    op.execute("DROP VIEW IF EXISTS grafana.qty_endpoints_per_user;")
    op.execute("DROP VIEW IF EXISTS grafana.process_state;")
    op.execute("DROP VIEW IF EXISTS grafana.inferred_user;")
    op.execute("DROP VIEW IF EXISTS grafana.endpoint_request;")
    op.execute("DROP VIEW IF EXISTS grafana.document_state_summary;")
    op.execute("DROP VIEW IF EXISTS grafana.corpus;")
