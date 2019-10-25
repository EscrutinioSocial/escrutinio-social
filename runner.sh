#!/bin/sh
# nohup python3 manage.py scheduler &
# nohup python3 manage.py importar_csv &
python3 manage.py runserver_plus --print-sql 0.0.0.0:8000
