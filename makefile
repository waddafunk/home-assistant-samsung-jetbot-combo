.PHONY: all clean install dev-install format lint test coverage build publish help

PYTHON := python3
PACKAGE := ./custom_components/samsung_jetbot_combo

help:
	@echo "Available commands:"
	@echo "  make install      - Install package for production"
	@echo "  make dev-install  - Install package with development dependencies"
	@echo "  make format       - Format code using black and isort"
	@echo "  make upgrade      - upgrade code using pyupgrade"
	@echo "  make lint         - Run code quality checks (pylint, flake8)"
	@echo "  make test         - Run tests with pytest"
	@echo "  make coverage     - Generate test coverage report"
	@echo "  make clean        - Remove build artifacts and cache files"
	@echo "  make build        - Build distribution packages"
	@echo "  make publish      - Publish package to PyPI"
	@echo "  make all          - Run all quality checks and tests"

install:
	$(PYTHON) -m pip install -r requirements.txt

dev-install:
	$(PYTHON) -m pip install -r requirements.txt

format:
	$(PYTHON) -m isort $(PACKAGE) 
	$(PYTHON) -m black $(PACKAGE) 
	

lint:
	$(PYTHON) -m pylint $(PACKAGE) 
	
