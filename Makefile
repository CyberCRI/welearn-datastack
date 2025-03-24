.PHONY: black-check
black-check:
	echo "== Black check =="
	python -m black --diff --check .
	echo "== end black check =="
	echo "====================="

.PHONY: black-fix
black-fix:
	echo "== Black fix =="
	python -m black .
	echo "== end black fix =="
	echo "====================="

isort-check:
	echo "== isort check =="
	python -m isort --profile black . -c
	echo "== end isort check =="
	echo "====================="

.PHONY: bandit-lint
bandit-lint:
	echo "== bandit lint =="
	python -m bandit -r welearn_datastack/ tests/ ./main.py
	echo "== end bandit lint =="
	echo "====================="


.PHONY: mypy-lint
mypy-lint:
	echo "== mpypy lint =="
	python -m mypy --exclude .venv/ --exclude .mypy_cache/ --exclude locustfiles/ --exclude alembic/ --show-error-codes --verbose .
	echo "== end mypy lint =="
	echo "====================="

.PHONY: format-check
format-check: isort-check black-check

.PHONY: lint
lint: bandit-lint

.PHONY: test
test:
	echo "Testing..."
	python -m unittest discover tests/
	echo "... done testing"
