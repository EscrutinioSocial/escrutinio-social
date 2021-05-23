Configuración de 
===========

Instalación con docker
----------------------

La forma más sencilla de configurar rápidamente un entorno de
desarrollo es usando docker. Para ello sólo necesitamos tener
instalado docker. La imagen se genera a partir del archivo
`Dockerfile` y utiliza como base `python:3.7-slim` sobre la que agrega
algunos paquetes.

Para crear la imagen se usa `docker-compose build`. Para poner en
línea el sitio local, se usa `docker-compose up -d`; esto crea, de ser
necesario la imagen también. La aplicación consta de dos contenedores:
`escrutinio-social-bd` y `escrutino-social-app`; el primero es para la
base de datos y el segundo es la aplicación django propiamente dicha.

El archivo `Makefile` define reglas para no tener que aprender a usar
docker forzosamente. Las más relevantes son:

`build`
  Crea las imágenes. Invoca `docker-compose build`

`up`
  Ejecuta el servicio en modo daemon, creando las imágenes si es necesario. (`docker-compose up -d`)

`setup-dev-data`
  Crea una elección mínima con pocas mesas; útil para testear la aplicación via web.

`stop`
  Detiene los servicios `-db` y `-app`.


Instalación local sin docker
----------------------------

Dependiendo la version de Python 3.7 puede no estar disponible. Puedes buscar el paquete de un tercero
(por ejemplo el PPA de deadsneaks en ubuntu)


```
sudo apt update
sudo apt install -y python3.7 python3.7-dev gdal-bin
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
mkdir ~/.virtualenvs
python3 -m venv ~/envs/escrutinio
source ~/envs/escrutinio/bin/activate
pip install -r requirements.txt


## configuracion

Definir tu escrutinio_social/local_settings.py teniendo en cuenta la nueva base

``` py
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


