UPDATE
	document_related.welearn_document wd
SET
	doi = REPLACE((details ->> 'doi'), 'https://doi.org/' , '')
WHERE
	wd.id IN :ids
	AND
	EXISTS (
	SELECT
		1
	FROM
		alembic_version
	WHERE
		version_num = :revision_id)