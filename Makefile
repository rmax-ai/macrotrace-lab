.PHONY: install format lint typecheck test coverage smoke clean

install:
	uv sync --group dev

format:
	ruff format .

lint:
	ruff check --fix

typecheck:
	mypy src/macrotrace

test:
	pytest -v --tb=short -x

coverage:
	pytest -v --tb=short --cov=src/macrotrace --cov-report=term-missing

smoke: install
	@echo "=== Smoke Test: Full Pipeline ==="
	python -m macrotrace init
	python -m macrotrace scenarios generate --count 20 --seed 42
	python -m macrotrace runs execute --experiment smoke_test --max-concurrency 4
	python -m macrotrace evals run --experiment smoke_test
	python -m macrotrace documents build --experiment smoke_test
	python -m macrotrace patterns discover --experiment smoke_test
	python -m macrotrace diagnose --experiment smoke_test --pattern top
	@echo "=== Smoke Test Complete ==="

ci: format lint typecheck coverage

clean:
	rm -rf data/
	rm -f macrotrace.db
	rm -rf .mypy_cache .ruff_cache .coverage htmlcov
