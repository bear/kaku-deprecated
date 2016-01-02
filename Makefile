

help:
	@echo "  deps        install dependencies"
	@echo "  clean       remove unwanted stuff"
	@echo "  lint        check style with flake8"
	@echo "  coverage    run tests with code coverage"
	@echo "  test        run tests"

deps:
	pip install -r requirements.txt --use-mirrors

clean:
	rm -fr build
	rm -fr dist
	find . -name '*.pyc' -exec rm -f {} \;
	find . -name '*.pyo' -exec rm -f {} \;
	find . -name '*~' -exec rm -f {} \;

lint:
	flake8 . > violations.flake8.txt

coverage:
	nosetests --with-coverage --cover-package=twitter

local:
	python kaku.py --logpath . --port 9999 --host 127.0.0.1 --config ./kaku.cfg
