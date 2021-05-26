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

Ingresar a [Digital Ocean](https://cloud.digitalocean.com/)

### Spaces

Crear una nueva instancia:

- Seleccionar la región (ej. San Francisco 3)
- Habilitar CDN
- Dejar restringido _File Listing_
- Elegir nombre único
- Seleccionar el proyecto

### Database

Crear un cluster de base de datos:

- Seleccionar Postgres 12
- Seleccionar la configuración del cluster: Basic nodes, 1GB RAM / 1vCPU / 10GB HD
- Seleccionar la región

Una vez que se termina de aprovisionar el cluster. Ir a _`Users & Databases`_ y crear el usuario y base de datos _escrutinio-social_.

### App Platform

Crear una _App_:

- Seleccionar el repositorio y el branch
- Dejar activado el _Autodeploy code changes_

A continuación se ofrece configurar el servicio principal. Dejar valores por defecto y pasar al siguiente paso. A continuación:

- Dejar el nombre por defecto
- Seleccionar la región que coincida con la seleccionada para la base de datos

Finalmente seleccionar el plan y la maquina para el container:

- Seleccionar el plan _Pro_
- Maquina 1GB RAM / 1vCPU

A continuación vamos a la solapa de configuración de la _App_.

- Seleccionar el _Component_ creado y borrarlo (_Destroy_)

Deberíamos quedar con una _App_ vacía.

A continuación vamos a cargar el archivo con toda la especificación:

- Hacer una copia del archivo `ci/do_templates/escrutinio-social.yaml` por fuera del repositorio git (no hacer commit de los cambios)
- Actualizar los valores marcados con el comentario `# completar`
- Desde la solapa de configuración de la _App_ cargar el archivo modificado, revisar y aceptar

Ir a la solapa de configuración de la _App_ y editar la sección de dominios:

- Agregar el dominio escrutinio.mueve.lat

Ir a la configuración del _Space_ y editar la sección de _CORS_ para aceptar solicitudes desde el dominio de la _App_
