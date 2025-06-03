.PHONY: black-check
black-check:
	black --diff --check .

.PHONY: black-fix
black-fix:
	black .

isort-check:
	isort --profile black . -c

.PHONY: bandit-lint
bandit-lint:
	python -m bandit -r welearn_datastack/ tests/ ./main.py


.PHONY: mypy-lint
mypy-lint:
	mypy --exclude .venv/ --exclude .mypy_cache/ --exclude locustfiles/ --exclude alembic/ --show-error-codes .

.PHONY: format-check
format-check: isort-check black-check

.PHONY: lint
lint: bandit-lint

.PHONY: test
test:
	echo "Testing..."
	python -m unittest discover tests/
	echo "... done testing"
