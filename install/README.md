# Instalar

## Paqueteria

```
sudo apt update
sudo apt install -y git python3-venv nginx postgresql postgresql-contrib gdal-bin postgis
# asegurate que sea al menos python 3.6
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

## El código

```
git clone https://github.com/OpenDataCordoba/escrutinio-social.git
cd escrutinio-social/
mkdir ~/envs
python3 -m venv ~/envs/escrutinio
source ~/envs/escrutinio/bin/activate
pip install -r requirements.txt 
./manage.py migrate
./manage.py collectstatic
```

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

## Web

Instalar supervisor y gunicorn.  
Usar letsencrypt para https segun tu servidor.  

## Datos

Definir la eleccion y sus opciones

### Importar guía electoral

 - Preparar la lista de lugares de votacion con las mesas asignadas a cada uno. 
 - Generar un importador que traiga los datos al sistema