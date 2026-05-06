SELECT
	id
FROM
	document_related.welearn_document
WHERE
	details ->> 'doi' IS NOT NULL
	AND doi IS DISTINCT
FROM
	(details ->> 'doi')
	AND details ->> 'doi' IS DISTINCT
FROM
	''
	AND EXISTS (
	SELECT
		1
	FROM
		alembic_version
	WHERE
		version_num = :revision_id
      )
ORDER BY
	id
LIMIT :batch_size