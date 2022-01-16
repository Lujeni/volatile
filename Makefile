PRJ := volatile
PKG := $(subst -,_,$(PRJ))

TAG ?= $(shell git describe --tags)
WHO ?= $(shell whoami)

REGISTRY ?=  $(shell echo registry.numberly.in/$(NS)/$(GROUP)/ | sed 's/\/\//\//')

IMG := $(REGISTRY)$(PRJ)

help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

build:	## build the current tag and latest version
	DOCKER_BUILDKIT=1 docker build --ssh default -t $(IMG):$(TAG) .
	DOCKER_BUILDKIT=1 docker build --ssh default -t $(IMG):latest .

push: build		## push the current tag and latest version [deps:build]
	docker push $(IMG):$(TAG)
	docker push $(IMG):latest

black-check:
	black --check $(PKG) tests

flake8-check:
	flake8 $(PKG) tests

isort-check:
	isort --diff $(PKG) tests

bandit-check:
	bandit -r $(PKG)

radon-check:
	radon cc -s -a $(PKG)
	radon mi -s $(PKG)

qa-check: black-check flake8-check isort-check radon-check bandit-check

black:
	black $(PKG) tests

isort:
	isort $(PKG) tests

qa:  black isort

safety:
	safety check -r requirements.txt

test:
	pytest
