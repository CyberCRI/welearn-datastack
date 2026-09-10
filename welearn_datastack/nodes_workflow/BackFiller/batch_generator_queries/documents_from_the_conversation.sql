SELECT
	id
FROM
	document_related.welearn_document wd
WHERE
	wd.corpus_id = 'c81878c8-586e-4346-8555-ad14ff356f17'
	AND EXISTS (
	-- Check if revision is the one we want before performing operation
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