.PHONY: up down restart logs crawl topics status clean

# Start all services
up:
	docker compose up -d --build
	@echo "✓ Services starting... Airflow UI → http://localhost:8080 (admin/admin)"

# Stop all services
down:
	docker compose down

# Restart everything
restart: down up

# View logs (usage: make logs s=kafka)
logs:
	docker compose logs -f $(s)

# Run a single crawl manually
crawl:
	docker compose exec airflow-scheduler \
		python -c "from crawlers.newspulse_crawler.run import run_all; run_all()"

# List Kafka topics
topics:
	docker compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Check service health
status:
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Wipe all data volumes
clean:
	docker compose down -v
	@echo "✓ All volumes removed"