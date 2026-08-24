.PHONY: setup besu-up besu-status deploy-contract init-identities ui smoke-test test lint besu-down reset-local run-chapter5

PYTHON ?= python

setup:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m app.cli setup

besu-up:
	$(PYTHON) -m scripts.besu_network up

besu-status:
	$(PYTHON) -m scripts.besu_network status

deploy-contract:
	$(PYTHON) -m app.cli deploy-contract

init-identities:
	$(PYTHON) -m app.cli init-identities --count 10

ui:
	$(PYTHON) -m streamlit run streamlit_app.py

smoke-test:
	$(PYTHON) -m app.cli smoke-test

test:
	$(PYTHON) -m pytest tests -q --ignore=tests/test_blockchain_integration.py
	$(PYTHON) -m pytest tests/test_blockchain_integration.py -q --tb=short || true

lint:
	$(PYTHON) -m ruff check app tests scripts
	$(PYTHON) -m black --check app tests scripts streamlit_app.py

besu-down:
	$(PYTHON) -m scripts.besu_network down

reset-local:
	$(PYTHON) -m app.cli reset-local --confirm

run-chapter5:
	$(PYTHON) -m scripts.run_chapter5_matrix
