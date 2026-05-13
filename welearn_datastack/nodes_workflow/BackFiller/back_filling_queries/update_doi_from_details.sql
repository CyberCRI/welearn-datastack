-- Extract DOI from JSON details and set it on the document,
-- skipping documents whose DOI already exists in the table (duplicates).
WITH updated AS (
UPDATE
	document_related.welearn_document wd
SET
	doi = REPLACE((details ->> 'doi'), 'https://doi.org/', '')
WHERE
	-- Only process the provided document IDs
	wd.id IN :ids
	-- Safety check: ensure the migration revision is applied
	AND EXISTS (
	SELECT
		1
	FROM
		alembic_version
	WHERE
		version_num = :revision_id
        )
	-- Skip if the cleaned DOI is already present in the table
	AND NOT EXISTS (
	SELECT
		1
	FROM
		document_related.welearn_document wd2
	WHERE
		wd2.doi = REPLACE((wd.details ->> 'doi'), 'https://doi.org/', '')
        )
    RETURNING id
),
-- Identify skipped documents by diffing :ids against successfully updated ones.
-- All skipped documents are considered duplicates since :ids only contains documents with a DOI.
skipped AS (
SELECT
	UNNEST(:ids::uuid[]) AS id
EXCEPT
SELECT
	id
FROM
	updated
)
-- Track the status of each document in the tmp table.
-- On conflict, update the status in case the document was reprocessed.
INSERT
	INTO
	tmp_document_doi_status (document_id,
	is_duplicate)
SELECT
	id,
	FALSE
FROM
	updated
UNION ALL
SELECT
	id,
	TRUE
FROM
	skipped