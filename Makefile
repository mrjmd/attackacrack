.PHONY: help lint test test-fast test-coverage security check-all install-dev clean

help:
	@echo "Available commands:"
	@echo "  make lint          - Run flake8 linting checks"
	@echo "  make test          - Run all tests in Docker"
	@echo "  make test-fast     - Run tests with fail fast"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make security      - Run security scan with bandit"
	@echo "  make check-all     - Run all checks (lint, security, tests)"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make clean         - Clean up generated files"

# Install development dependencies
install-dev:
	pip install flake8 bandit pytest pytest-cov

# Linting
lint:
	@echo "Running lint checks..."
	@flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics \
		--exclude=.git,__pycache__,docs,old_env,venv,env,.venv,migrations,node_modules
	@flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics \
		--exclude=.git,__pycache__,docs,old_env,venv,env,.venv,migrations,node_modules

# Security scan
security:
	@echo "Running security scan..."
	@bandit -r . -f json -o bandit-report.json \
		--skip B101 \
		-x '.git,__pycache__,docs,old_env,venv,env,migrations,tests' || true
	@echo "Security report saved to bandit-report.json"

# Testing
test:
	@echo "Running tests in Docker..."
	docker-compose exec web pytest

test-fast:
	@echo "Running tests with fail fast..."
	docker-compose exec web pytest -x

test-coverage:
	@echo "Running tests with coverage..."
	docker-compose exec web pytest --cov=. --cov-report=html --cov-config=.coveragerc
	@echo "Coverage report saved to htmlcov/"

# Run all checks
check-all: lint security test
	@echo "All checks completed!"

# Clean up
clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -rf htmlcov/ .coverage bandit-report.json
	@echo "Clean complete!"

# Quick check before pushing
pre-push: lint
	@echo "Quick pre-push checks passed!"