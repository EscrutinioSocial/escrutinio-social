# Instalar


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

## Datos

Definir la eleccion y sus opciones

### Importar guía electoral

 - Preparar la lista de lugares de votacion con las mesas asignadas a cada uno. 
 - Generar un importador que traiga los datos al sistema