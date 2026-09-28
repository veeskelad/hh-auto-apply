.PHONY: install run auth docker-up docker-down clean

# Локальная установка
install:
	pip install -r requirements.txt
	playwright install chromium

# Запуск дашборда
run:
	python web_app.py

# Первичная авторизация на HH.ru (откроет браузер — войди по SMS)
auth:
	python auth_once.py

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

# Очистка данных (аккуратно!)
clean:
	rm -rf data/applied_vacancies.json data/interviews.json data/notifications/*.json

# Создать .env из примера
setup-env:
	cp -n .env.example .env || true
	@echo "⚙️  Заполни .env перед запуском"
