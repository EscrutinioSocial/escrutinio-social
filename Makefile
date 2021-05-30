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
	docker-compose run app bash

shell-db:
	docker-compose run db bash

shell_plus:
	docker-compose run app python manage.py shell_plus

log-app:
	docker-compose logs -f app

log-scheduler:
	docker-compose logs -f scheduler

log-db:
	docker-compose logs -f db

test:
	docker-compose run --rm app pytest

test-exec:
	docker-compose exec app pytest --cov-report=html

collectstatic:
	docker-compose run app python manage.py collectstatic --noinput

create:
	docker-compose up --no-start

migrate:
	docker-compose run app python manage.py migrate

makemigrations:
	docker-compose run app python manage.py makemigrations

setup-dev-data: migrate
	docker-compose run app python manage.py loaddata fixtures/dev_data.json

dump-dev-data:
	docker-compose run app python manage.py dumpdata auth.Group auth.User fiscales.Fiscal elecciones --indent=2 > fixtures/dev_data.json"

update-models-diagram:
	docker-compose run app python manage.py graph_models fiscales elecciones adjuntos --output docs/_static/models.png

crawl-resultados:
	docker exec escrutinio-social-app /bin/sh -c "./crawl_resultados.sh $(tipoDeAgregacion) $(opcionaConsiderar)"

crawl-resultados-up:
	docker exec escrutinio-social-app /bin/sh -c "python simple-cors-http-server.py"

test-e2e:
	cd e2e;npm i;npm test;

test-e2e-headless:
	cd e2e;npm i;npm run test-headless;

app-platform-env='$${AWS_ACCESS_KEY_ID} $${AWS_SECRET_ACCESS_KEY} $${AWS_STORAGE_BUCKET_NAME} $${AWS_S3_ENDPOINT_URL} $${DB_CLUSTER_NAME} $${APP_REGION} $${APP_DOMAIN} $${APP_NAME} $${DJANGO_SECRET_KEY} $${GUNICORN_WORKERS} $${GITHUB_REPO} $${BRANCH_NAME} $${IMAPS_CONFIG}'
app-platform-template = ci/do_templates/app-platform.yaml.tpl

test-app-platform-spec:
	shdotenv -e .env-deploy envsubst $(app-platform-env) <$(app-platform-template)

create-app-platform-deploy:
	shdotenv -e .env-deploy envsubst $(app-platform-env) <$(app-platform-template) | doctl apps create --spec -

update-app-platform-deploy:
	shdotenv -e .env-deploy envsubst $(app-platform-env) <$(app-platform-template) | doctl apps update $(app-id) --spec -
