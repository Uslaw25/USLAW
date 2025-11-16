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

# SSL Certificate Management
ssl-help:
	@echo "Usage: make [env].ssl DOMAIN=example.org         # fetch real certificates"
	@echo "       make [env].ssl.dummy DOMAIN=example.org   # fetch dummy certificates"
	@echo "Where [env] is: dev, prod"

%.ssl:
	@if [ -z "$(DOMAIN)" ]; then echo "Error: DOMAIN parameter is required"; exit 1; fi
	@$($*_compose) down
	@sudo ./init-letsencrypt.sh $(DOMAIN) 0 docker-compose.$*.yml # fetch real certificates
	@$($*_compose) up -d

%.ssl.dummy:
	@if [ -z "$(DOMAIN)" ]; then echo "Error: DOMAIN parameter is required"; exit 1; fi
	@$($*_compose) down
	@sudo ./init-letsencrypt.sh $(DOMAIN) 1 docker-compose.$*.yml # fetch dummy certificates
	@$($*_compose) up -d