SHELL := /bin/sh

.PHONY: build up down logs ps shell restart clean

build:
	docker compose build

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

shell:
	docker compose exec web sh

restart:
	docker compose restart

clean:
	docker compose down --volumes --remove-orphans
