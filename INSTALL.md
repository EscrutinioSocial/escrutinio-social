# Instalación de un entorno de desarrollo

Escrutinio Social es un proyecto basado en Django (2.2), postgresql (9.6 o superior) y python 3.7.
Si bien no usamos postgis, hay un paquete que requiere gdal-bin instalado en tu sistema.

Dependiendo la version de Python 3.7 puede no estar disponible. Puedes buscar el paquete de un tercero
(por ejemplo el PPA de deadsneaks en ubuntu)

## Instalación de un


```
sudo apt update
sudo apt install -y python3.7 python3.7-dev gdal-bin postgresql
```

## Crear una base de datos
Dar de alta la base
```
sudo su - postgres
psql
```

``` sql
CREATE USER escrutinio_user WITH PASSWORD 'escrutinio_pass';
ALTER ROLE escrutinio_user SUPERUSER;
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
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
