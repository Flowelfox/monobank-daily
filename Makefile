.PHONY: run install test lint format compile-translations clean

run:
	uv run monobankdaily

install:
	uv sync

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

compile-translations:
	msgfmt -o locales/uk/LC_MESSAGES/messages.mo locales/uk/LC_MESSAGES/messages.po
	msgfmt -o locales/en/LC_MESSAGES/messages.mo locales/en/LC_MESSAGES/messages.po

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/*.db 2>/dev/null || true
