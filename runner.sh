#!/bin/sh
nohup python3 manage.py createcachetable
nohup python3 manage.py scheduler &
nohup python3 manage.py importar_csv &
python3 manage.py runserver 0.0.0.0:8000
