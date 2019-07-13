build:
	docker-compose build

up:
	docker-compose up -d

up-non-daemon:
	docker-compose up

start:
	docker-compose start

stop:
	docker-compose stop

restart:
	docker-compose stop && docker-compose start

down:
	docker-compose down --volumes

shell-app:
	docker exec --interactive --tty escrutinio-social-app /bin/bash

shell-db:
	docker exec --interactive --tty escrutinio-social-db /bin/bash

log-app:
	docker-compose logs app

log-db:
	docker-compose logs db

collectstatic:
	docker exec escrutinio-social-app /bin/sh -c "python manage.py collectstatic --noinput"


test:
	docker exec escrutinio-social-app /bin/sh -c "pytest"

create:
	docker-compose up --no-start

migrate: up
	docker exec escrutinio-social-app /bin/sh -c "python manage.py migrate"

setup-dev-data: migrate
	docker exec escrutinio-social-app /bin/sh -c "python manage.py loaddata fixtures/dev_data.json"

dump-dev-data:
	python manage.py dumpdata auth.Group auth.User fiscales.Fiscal elecciones --indent=2 > fixtures/dev_data.json

update-models-diagram:
	python manage.py graph_models fiscales elecciones adjuntos --output docs/_static/models.png

crawl-resultados:
	 wget --recursive --level=100 --convert-links --html-extension --restrict-file-names=windows --no-parent --no-host-directories --directory-prefix=crawl-resultados --span-hosts localhost:8000/elecciones/resultados/1
	 find crawl-resultados -type f -name "*.html*" -exec sed -i 's/http:\/\/localhost:8000//g' {} +
	 find crawl-resultados -type f -name "*.html*" -exec sed -i '/href="\/login\/"/d' {} +
	 find crawl-resultados -type f -name "*.html*" -exec sed -i "s/id='tipodesumarizacion'/id='tipodesumarizacion' style='display:none'/g" {} +

crawl-resultados-up:
	docker exec escrutinio-social-app /bin/sh -c "python simple-cors-http-server.py"
