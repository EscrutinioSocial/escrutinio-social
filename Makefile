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

shell_plus:
	docker exec --interactive --tty escrutinio-social-app python manage.py shell_plus

log-app:
	docker-compose logs app

log-db:
	docker-compose logs db

test:
	docker-compose run --rm app pytest --cov=. --cov-report=html --cov-fail-under=52

test-exec:
	docker-compose exec app pytest --cov=. --cov-report=html --cov-fail-under=52

collectstatic:
	docker exec escrutinio-social-app /bin/sh -c "python manage.py collectstatic --noinput"

create:
	docker-compose up --no-start

migrate: up
	docker exec escrutinio-social-app /bin/sh -c "python manage.py migrate"

makemigrations: up
	docker exec escrutinio-social-app /bin/sh -c "python manage.py makemigrations"

setup-dev-data: migrate
	docker exec escrutinio-social-app /bin/sh -c "python manage.py loaddata fixtures/dev_data.json"

dump-dev-data:
	docker exec escrutinio-social-app /bin/sh -c "python manage.py dumpdata auth.Group auth.User fiscales.Fiscal elecciones --indent=2 > fixtures/dev_data.json"

update-models-diagram:
	python manage.py graph_models fiscales elecciones adjuntos --output docs/_static/models.png

crawl-resultados:
	docker exec escrutinio-social-app /bin/sh -c "./crawl_resultados.sh $(tipoDeAgregacion) $(opcionaConsiderar)"

crawl-resultados-up:
	docker exec escrutinio-social-app /bin/sh -c "python simple-cors-http-server.py"

test-e2e:
	cd e2e;npm i;npm test;

test-e2e-headless:
	cd e2e;npm i;npm run test-headless;

# Small Makefile to ease up the execution of tests and operating the Devel env
#VERSION=1.0
#ECS_Cluster=Convencer-Test
#ISRUN=$(shell [[ `docker-compose ps -q` ]] && echo 'yes' || echo 'no')
#
#.PHONY: help
#
#help: ## This help
#	@echo '--------------------------------------------------------------------------------------------------------------------'
#	@echo '                                                                                                                    '
#	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
#
#.DEFAULT_GOAL := help
#
#list: ## List what is running of the Development environment
#	@docker-compose ps
#
#build: ## Build the containers of the Development environment not using the cache
#	@docker-compose build --no-cache
#
#run: ## Bring the whole development environment UP
#	@docker-compose up -d
#
#force_clean: ## Forced clean up including volumes
#	@docker-compose down --rmi local -v
#
#stop: ## Stop the whole development thingy
#	@docker-compose down
#
#rm: ## Just an alias of the previous one (stop)
#	stop
#
#clean: ## Stop running containers and clean up all images of the Development environment
#	@docker-compose down --rmi local
#
#push: ## Logging in to the ECR and push the Image to it. Usage: make push image=927223451584.dkr.ecr.sa-east-1.amazonaws.com/image_name
#	@eval $$(aws ecr get-login --no-include-email)
#	@docker push $(image)
#
#list_tasks_definitions: ## List the tasks defined in the Cluster
#	@echo "Listing tasks defined in the Cluster"
#	@aws ecs list-task-definitions
#
#list_tasks: ## List tasks running on the Cluster
#	@echo "Listing running tasks"
#	@aws ecs list-tasks --cluster $(ECS_Cluster)
#
#list_services: ## List Services created in the Cluster
#	@echo "Listing Services in $(ECS_Cluster) Cluster"
#	@aws ecs list-services --cluster $(ECS_Cluster) | jq .serviceArns
#
#create_task_definition: ## Create a new task definition (task family matters) or update an existing one based on a json template
#	@aws ecs register-task-definition --cli-input-json file://$(filename)
#
#delete_task_definition: ## Deletes a task defined in the Cluster. Requires task-id
#	@echo "Deleting task-definition $(task-id)"
#	@aws ecs deregister-task-definition --task-definition $(task-id)
#
#create_service: ## Create a new service. Parameters required: service-name, task-definition, replicas.
#	@echo "Creating Service $(service-name)"
#	@aws ecs create-service --cluster $(ECS_Cluster) --service-name $(service-name) --task-definition $(task-definition) --desired-count $(replicas) --launch-type "EC2"
#
#update_service: ## Update the number of replicas of an existing service. Requires service-name and replicas.
#	@echo "Updating service $(service-name)"
#	@aws ecs update-service --service $(service-name) --desired-count $(replicas) --cluster $(ECS_Cluster)
#
#delete_service: ## Delete a service. Requires, service-name
#	@echo "Deleting Service $(service-name)"
#	@aws ecs update-service --service $(service-name) --desired-count 0 --cluster $(ECS_Cluster)
#	@aws ecs delete-service --service $(service-name) --cluster $(ECS_Cluster)
#
#service_events: ## Check the events from a service. Requires service-name.
#	@echo "Listing events for service $(service-name)"
#	@aws ecs describe-services --cluster Convencer-Test --services $(service-name) | jq '.services[0]|.events[]'
#
#version: ## Output the version
