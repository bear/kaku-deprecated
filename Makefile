help:
	@echo "  env         install all dependencies"
	@echo "  dev         install all development dependencies"
	@echo "  clean       remove unwanted stuff"
	@echo "  lint        lint with flake8"
	@echo "  test        run tests"
	@echo "  coverage    run codecov"

info:
	pipenv --version
	pipenv run python --version

env:
	pipenv install --python 3.9

dev:
	pipenv install --dev

clean:
	rm -rf build
	rm -rf dist
	rm -f violations.flake8.txt
	find . -name '*.pyc' -exec rm -f {} \;
	find . -name '*.pyo' -exec rm -f {} \;
	find . -name '*~' -exec rm -f {} \;

lint: clean
	pipenv run black src tests
	pipenv run flake8 src tests --tee --output-file=violations.flake8.txt

test: lint
	pipenv install --dev "-e ."
	pipenv run pytest

coverage: test
	pipenv run coverage run -m pytest
	pipenv run coverage report
	pipenv run coverage html
	pipenv run codecov

check: lint
	pipenv run check-manifest -v

dist: check
	pipenv run python -m build

upload: dist
	pipenv run python -m twine upload --repository testpypi dist/*

upload-prod: dist
	pipenv run python -m twine upload dist/*
