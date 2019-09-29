#!/bin/sh
nohup python3 manage.py consolidar_identificaciones_y_cargas &
nohup python3 manage.py importar_csv &
python3 manage.py runserver 0.0.0.0:8000
