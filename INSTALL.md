# Instalación de un entorno de desarrollo

Escrutinio Social es un proyecto basado en Django (2.2), postgresql (9.6 o superior) y Python 3.7.
Hemos puesto esfuerzo en simplificar todo lo posible el setup de un entorno de desarrollo

Para poner en marcha este entorno necesitamos contar con [docker](https://docs.docker.com/engine/installation/) y [docker-compose](https://docs.docker.com/compose/install/). Puedes seguir las instrucciones oficiales correspondientes a tu sistema operativo.

Para crear e inicializar los contenedores,

```
make build
make setup-dev-data
```

Para lanzar los servicios y la aplicación

```
make up
make shell-app
root@8e90b4b0175f:/src# python manage.py createcachetable
```

Luego podrás ingresar a http://localhost:8000/ y loguearte con `admin` / `admin`. Este usuario, además de ser fiscal (es decir, dataentry), tiene privilegios de superusuario, habilitándolo a subir actas.

Para detener los servicios de docker:

```
make stop
```

Los datos sintéticos que se cargan se tratan de una elección con tres opciones, 8 mesas (mesa 1 a 8) divididas en 2 secciones y 4 circuitos.

Una vez logueado, podés subir imágenes desde la opción "Subir actas" y asociarlas a alguna de las mesas. Eso te habilitará la opción de cargar actas y luego computar resultados.

Hay más comandos que pueden ser útiles.

- `make shell-app` y `make shell-db` para entrar a la consola de los contenedores
- `make log-app` y `make log-db` para ver el dump de outputs capturados
- `make down` para remover los contenedores y sus volúmenes de datos (para un fresh install)
- y más. Revisá el código de `Makefile`

## Instalación local

Si preferís no usar Docker podés seguir las [instrucciones para armar un entorno de desarrollo local](https://github.com/OpenDataCordoba/escrutinio-social/wiki/Instalaci%C3%B3n-de-un-entorno-de-desarrollo-local) en nuestra wiki.

## Despliege a Digital Ocean

Ingresar a [Digital Ocean](https://cloud.digitalocean.com/) y [habilitar la integración con Github](https://cloud.digitalocean.com/apps/github/install) para el repositorio y branch que corresponda.

### Spaces

Crear una nueva instancia:

- Seleccionar la región (ej. San Francisco 3)
- Habilitar CDN
- Dejar restringido _File Listing_
- Elegir nombre único
- Seleccionar el proyecto

Ir a la configuración del _Space_ y editar la sección de _CORS_ para aceptar solicitudes desde el dominio de la aplicación

### Database

Crear un cluster de base de datos:

- Seleccionar la base de datos (Postgres 12)
- Seleccionar la configuración del cluster: Basic nodes, 1GB RAM / 1vCPU / 10GB HD
- Seleccionar la región (ej. nyc)

Una vez que se termina de aprovisionar el cluster. Ir a _`Users & Databases`_ y crear el usuario y base de datos _escrutinio-social_.

### App Platform

#### Setup

```bash
doctl auth init --context <name>
doctl auth switch --context <name>

curl -L https://github.com/ko1nksm/shdotenv/releases/latest/download/shdotenv --output /usr/local/bin/shdotenv
chmod +x /usr/local/bin/shdotenv
```

Crear un archivo .env-deploy y definir las siguientes variables:

```bash
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_ENDPOINT_URL=
DB_CLUSTER_NAME=
APP_REGION=
APP_DOMAIN=
APP_NAME=
DJANGO_SECRET_KEY=
GUNICORN_WORKERS=
GITHUB_REPO=
BRANCH_NAME=
IMAPS_CONFIG=
```

#### Test

Para inspeccionar la especificación luego del reemplazo de variables de entorno:

```bash
make test-app-platform-spec
```

#### Create

Para hacer el despliegue por primera vez:

```bash
make create-app-platform-deploy
```

#### Update

Para aplicar una actualización de la especificación, obtener el ID de la aplicación:

```bash
doctl apps list
```

luego, reemplazando el `<app-id>` con el valor que corresponda:

```bash
make update-app-platform-deploy app-id=<app-id>
```
