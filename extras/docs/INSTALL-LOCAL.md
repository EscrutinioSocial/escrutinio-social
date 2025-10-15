Contexto:
 - Python 3.10
 - Django 4.2
 - PSQL 15

```
sudo apt update
sudo apt install -y python3.10 python3.10-dev python3.10-venv gdal-bin poppler-utils
```

## Crear una base de datos
Dar de alta la base con postgis
```
sudo su - postgres
psql
```

``` sql
CREATE USER escrutinio_user WITH PASSWORD 'escrutinio_pass';
ALTER ROLE escrutinio_user SUPERUSER;
CREATE EXTENSION postgis;
CREATE DATABASE escrutinio_db OWNER escrutinio_user;
```

## Instalación del entorno virtual

```
git clone https://github.com/OpenDataCordoba/escrutinio-social.git
cd escrutinio-social/
python3.X -m venv ~/envs/escrutinio
source ~/envs/escrutinio/bin/activate
pip install -r requirements.txt
```

## Test
Para correr los tests

```
pytest -v
```

## Configuracion

Definir tu escrutinio_social/local_settings.py teniendo en cuenta la nueva base

```py
# Requiere una base de datos postgres con postgis activado
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'escrutinio_db',
        'USER': 'escrutinio_user',
        'HOST': 'localhost',
        'PASSWORD': 'escrutinio_pass',
        'PORT': 5432,
    }
}
```

Estamos en condiciones de crear las tablas.


```
./manage.py migrate
```

### Cache table

Esto es requerido para la URL /admin/constance/config/

```
python manage.py createcachetable
```

## Datos

Lo primero que debes hacer es crear un usuario superuser. Luego este usuario lo debes asociar
a un "Fiscal" desde /admin


```
./manage.py createsuperuser
```

Alternativamente podés usar el registro "Quiero ser fiscal" y luego convertir el usuario asociado a superusuario.



Para importar datos sintéticos (de prueba) de eleccion, categoría, mesas, por ahora podés usar la estructura de la última eleccion de Córdoba

```
./manage.py importar_carta_marina_2019_gobernador

# traer datos de las mesas
./manage.py importar_mesas_2019_gobernador

# Traer los partidos que participan con el orden de las actas
./manage.py importar_partidos_cba_2019

# Crear las opciones para la carga de datos
./manage.py crear_opciones_elecciones
```