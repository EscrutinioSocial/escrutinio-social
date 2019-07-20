#!/bin/bash

echo "Applying migrations, fixtures and running the service"
python manage.py migrate
python manage.py loaddata fixtures/dev_data.json
python manage.py runserver 0.0.0.0:8000

