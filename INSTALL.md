# Instalación de un entorno de desarrollo

Escrutinio Social es un proyecto basado en Django (2.2), postgresql (9.6 o superior) y Python 3.7.
Hemos puesto esfuerzo en simplificar todo lo posible el setup de un entorno de desarrollo

Para levantar el proyecto necesitamos contar con [docker](https://docs.docker.com/engine/installation/) y [docker-compose](https://docs.docker.com/compose/install/).

Para crear e inicializar los contenedores,

```
make build
make setup-dev-data
```

Para levantar los servicios y lanzar la aplicación

```
make up
```

Luego podrás ingresar a http://localhost:8000/ y loguearte con `admin` / `admin`. Este usuario, además de ser fiscal (es decir, dataentry), tiene privilegios de superusuario, habilitándolo a subir actas.

Para detener los servicios de docker:

```
make stop
```

Los datos sintéticos que se cargan se tratan de una elección con tres opciones, 8 mesas (mesa 1 a 8) divididas en 2 secciones y 4 circuitos.

Una vez logueado, podés subir imágenes desde la opción "Subir actas" y asociarlas a alguna de las mesas. Eso te habilitará la opción de cargar actas y luego computar resultados.


Hay más comandos en el Makefile, que pueden ser útiles.
- `shell-app` y `shell-db` para entrar a la consola de los contenedores
- `log-app` y `log-db` para ver el dump de outputs capturados
- `down` para remover los contenedores y sus volúmenes de datos (para un fresh install?)
- y más.

## Instalación local

Si preferís no usar docker podés seguir las [instrucciones para armar un entorno de desarrollo local](https://github.com/OpenDataCordoba/escrutinio-social/wiki/Instalaci%C3%B3n-de-un-entorno-de-desarrollo-local
) en nuestra wiki.