SHELL=/bin/bash

dev_compose    := docker compose -f docker-compose.dev.yml
prod_compose   := docker compose -f docker-compose.prod.yml


%.all: %.build %.up.d
	@echo $(success)

%.deploy: %.build %.down %.up.d
	@echo $(success)

%.build:
	@$($*_compose) build

%.up:
	@$($*_compose) up

%.up.d:
	@$($*_compose) up -d

%.down:
	@$($*_compose) down --remove-orphans

%.restart:
	@$($*_compose) restart

%.logs:
	@$($*_compose) logs -f

%.attach:
	@docker attach $*

