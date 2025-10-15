# Despliegue en producción

Hay 4 componentes

- Aplicación web (wsgi)
- Base de datos Postgresql
- Demonios (scheduler, consolidador, importador de actas desde email)
- Archivos estáticos de la aplicacion y subidos por los usuarios


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

