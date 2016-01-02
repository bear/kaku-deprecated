

help:
	@echo "  deps        install dependencies"
	@echo "  clean       remove unwanted stuff"
	@echo "  lint        check style with flake8"
	@echo "  local       run kaku in Flask's debug mode with the local config file"

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

local:
	@echo "make sure Redis is running..."
	python kaku.py --logpath . --port 9999 --host 127.0.0.1 --config ./kaku.cfg
