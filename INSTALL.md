# Instalación de un entorno de desarrollo

Escrutinio Social es un proyecto basado en Django (2.2), postgresql (9.6 o superior) y Python 3.7.
Hemos puesto esfuerzo en simplificar todo lo posible el setup de un entorno de desarrollo

Para levantar el proyecto necesitamos contar con [docker](https://docs.docker.com/engine/installation/) y [docker-compose](https://docs.docker.com/compose/install/).

Para crear e inicializar los contenedores,

```
make build
make setup-dev-data
```

Para levantar los servicios

```
make up
```

Luego puedes ingresar a http://localhost:8000/ y loguearte con `admin` / `admin`. Este usuario, además de ser fiscal, tiene privilegios de superusuario.

Los datos sintéticos que se cargan se tratan de una elección con tres opciones, 8 mesas (mesa 1 a 8) divididas en 2 secciones y 4 circuitos.

Una vez logueado, podés subir imágenes desde la opción "Subir actas" y asociarlas a alguna de las mesas.


## Instalación local

Si preferís no usar docker podés seguir las [instrucciones para armar un entorno de desarrollo local](https://github.com/OpenDataCordoba/escrutinio-social/wiki/Instalaci%C3%B3n-de-un-entorno-de-desarrollo-local
) en nuestra wiki.