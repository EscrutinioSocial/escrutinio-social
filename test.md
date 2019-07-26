# Tests unitarios

El proyecto utiliza [pytest](https://pytest.org/en/latest/) via [pytest-django](https://pytest-django.readthedocs.io)
para escribir y ejecutar pruebas unitarias.

Para corer los tests usando Docker

```
$ make test
```

Alternativamente, si usás un entorno local (o desde el shell del contenedor de la app, `make shell-app`)
podes correr

```
$ pytest
```

Podés correr un test en particular

```
$ pytest path_to/test_file.py::test_a_correr
```

O más en general

```
$ pytest -k test_a_correr
```

El test runner de pytest tiene muchas opciones útiles. Ver `--sw`, `--lf`, `-s` y más.

Tené en cuenta que por defecto la base de datos de tests se reusa (setting `--reuse-db`, definido en `pytest.ini`)
Eventualmente, la base puede divergir y los tests fallan porque faltan o sobran columnas.

Para reconstruir la base al estado actual, ejecutar

```
$ pytest --create-db

```

Hay un threshold de **cobertura de tests** mínimo definido en `pytest.ini` con el parámetro
`--cov-fail-under`. Esto significa que cualquier código que se agrega debe incoporar las pruebas
suficientes para no bajar de este nivel de cobertura.

No se aceptarán integraciones de cambios que modifiquen este cambio a menos, salvo una
muy justificada explicación.

Si en cambio, tu branch aumenta la cobertura (porque hiciste tests que
faltaban o borraste código muerto) por favor, aumentá ese valor al entero menor más próximo de
la cobertura que lograste. ¡Gracias!


## Pruebas de integación "end to end"

También hay pruebas "end to end" basadas en Cypress

Primero hay que levantar la app (Ver `Instalación <./INSTALL.md>`).

Para correr cypress c/ide:

```
make test-e2e
```

Para correr cypress headless:

```
make test-e2e-headless
```
