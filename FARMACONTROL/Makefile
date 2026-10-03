up:
	docker compose up -d --build

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100

backup:
	docker compose exec -T db sh -c 'mysqldump -uroot -p"$$MYSQL_ROOT_PASSWORD" --routines medicalife' > respaldo_$$(date +%Y%m%d_%H%M).sql

reset-db:
	docker compose down -v && docker compose up -d --build

.PHONY: up down ps logs backup reset-db
