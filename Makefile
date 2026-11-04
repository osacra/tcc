.PHONY: test coverage quality check

PYTHON ?= python3

test:
	$(PYTHON) -m pytest -q

coverage:
	coverage run -m pytest -q
	coverage report --show-missing --fail-under=90

quality:
	ruff check .
	black --check .

check:
	$(PYTHON) manage.py check
	$(MAKE) quality
	$(MAKE) test
