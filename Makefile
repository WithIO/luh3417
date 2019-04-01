PYTHON_BIN ?= python
ENV ?= pypitest

format: isort black

black:
	'$(PYTHON_BIN)' -m black setup.py
	'$(PYTHON_BIN)' -m black bin
	'$(PYTHON_BIN)' -m black src

isort:
	'$(PYTHON_BIN)' -m isort -rc setup.py
	'$(PYTHON_BIN)' -m isort -rc bin
	'$(PYTHON_BIN)' -m isort -rc src

convert_doc:
	pandoc -f markdown -t rst -o README.txt README.md

build: convert_doc
	python setup.py sdist

upload: convert_doc
	python setup.py sdist upload -r $(ENV)

venv: requirements.txt
	'$(PYTHON_BIN)' -m pip install -r requirements.txt

requirements.txt: FORCE
	'$(PYTHON_BIN)' -m piptools compile requirements.in

FORCE:
