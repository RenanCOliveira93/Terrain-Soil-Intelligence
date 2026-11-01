.PHONY: install api web test test-net e2e notebooks sample openapi check
install:
	python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cd frontend && npm install
api:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
web:
	cd frontend && npm run dev
test:
	.venv/bin/pytest tests -q && cd frontend && npm run typecheck && npm test
test-net:
	TSI_RUN_NETWORK=1 .venv/bin/pytest tests -q
e2e:
	cd frontend && npm run build && cd .. && TSI_RUN_E2E=1 .venv/bin/pytest tests/e2e -q
notebooks:
	.venv/bin/python scripts/build_notebooks.py
sample:
	.venv/bin/python scripts/build_sample_data.py && .venv/bin/python scripts/make_sample_polygons.py
openapi:
	.venv/bin/python scripts/export_openapi.py
check:
	.venv/bin/python scripts/check_infra.py
