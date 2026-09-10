
UPDATE
	document_related.welearn_document
SET
	external_id = substring(url, '\d+$')
WHERE
	id IN UNNEST(:ids)