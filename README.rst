Escrutinio Social
=================
Master

.. image:: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/badges/master/pipeline.svg?
   :target: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/pipelines

.. image:: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/badges/master/coverage.svg?
   :target: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/tree/master


.. image:: https://readthedocs.org/projects/escrutinio-social/badge/?version=latest
   :target: https://escrutinio-social.readthedocs.io/es/latest/?badge=latest
   :alt: Documentation Status

Develop

.. image:: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/badges/develop/pipeline.svg?
   :target: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/pipelines

.. image:: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/badges/develop/coverage.svg?
   :target: https://gitlab.e-va.red/escrutinio/escrutinio-paralelo/tree/develop





Escrutinio Social es una plataforma web para la realización de un escrutinio provisorio y auditoría
ciudadana a partir de fotos documentos aportados por fiscales partidarios o extraídos del escrutinio oficial.

Está basada en el framework Django y un stack de tecnologías libres.


:Licencia: BSD
:Slack: Sumate a la `sala de chat del proyecto <https://join.slack.com/t/opendatacba/shared_invite/enQtNjQ4OTY5MTg3Nzk2LTgxMDU5NTY1MWNmZTdkMzVmM2EyNmUwZGQ0Nzg0ZjdlNjBkZmI0Zjc2MTllMWZhZjAzMTEwMjAwYzk3NGNlMzk>`__
:Documentación: https://escrutinio-social.readthedocs.io/

Leé nuestro `Call for Constributors <https://github.com/OpenDataCordoba/escrutinio-social/wiki/Call-for-contributors>`__ y sumate al desarrollo.


Instalación
-----------

Ver `Instalación <./INSTALL.md>`__

Test
-----------

Ver `Test <./test.md>`__

Visualizaciones
-----------

Para generar las visualizaciones estáticas hacer:
```
$ make collectstatic
$ make crawl-resultados
```

Para ver las visualizaciones:
```
$ make crawl-resultados-up
```
y navegar a: http://localhost:8080/crawl-resultados/elecciones/resultados/1.html

Para deployar las visualizaciones en S3:
* copiar la carpeta static
* copiar la carpeta crawl-resultados
* habilitar cors (para que pueda cargar las fonts): https://docs.aws.amazon.com/AmazonS3/latest/dev/cors.html
