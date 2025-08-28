-- Academic scientific publications
WITH ids AS (
INSERT
	INTO
		corpus_related.category(title)
	VALUES
		('academic scientific publications')
    RETURNING id AS catid
)
UPDATE
	corpus_related.corpus
SET
	category_id = ids.catid
FROM
		ids
WHERE
	corpus.source_name IN ('hal', 'plos', 'peerj', 'oapen', 'openalex', 'open-edition-books');

-- Teaching resources
WITH ids AS (
INSERT
	INTO
		corpus_related.category(title)
	VALUES
		('teaching resources')
    RETURNING id AS catid
)
UPDATE
	corpus_related.corpus
SET
	category_id = ids.catid
FROM
		ids
WHERE
	corpus.source_name IN ('uved');

-- expert reports
WITH ids AS (
INSERT
	INTO
		corpus_related.category(title)
	VALUES
		('expert reports')
    RETURNING id AS catid
)
UPDATE
	corpus_related.corpus
SET
	category_id = ids.catid
FROM
		ids
WHERE
	corpus.source_name IN ('ipcc', 'ipbes');

-- science communication and outreach
WITH ids AS (
INSERT
	INTO
		corpus_related.category(title)
	VALUES
		('science communication and outreach')
    RETURNING id AS catid
)
UPDATE
	corpus_related.corpus
SET
	category_id = ids.catid
FROM
		ids
WHERE
	corpus.source_name IN ('conversation', 'ted');


-- collaborative and encyclopedic knowledge
WITH ids AS (
INSERT
	INTO
		corpus_related.category(title)
	VALUES
		('collaborative and encyclopedic knowledge')
    RETURNING id AS catid
)
UPDATE
	corpus_related.corpus
SET
	category_id = ids.catid
FROM
		ids
WHERE
	corpus.source_name IN ('wikipedia');

