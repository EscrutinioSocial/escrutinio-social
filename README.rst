Escrutinio Social
=================

.. image:: https://travis-ci.org/OpenDataCordoba/escrutinio-social.svg?branch=master
   :target: https://travis-ci.org/OpenDataCordoba/escrutinio-social

.. image:: https://coveralls.io/repos/github/OpenDataCordoba/escrutinio-social/badge.svg?branch=master
   :target: https://coveralls.io/github/OpenDataCordoba/escrutinio-social?branch=master


.. image:: https://readthedocs.org/projects/escrutinio-social/badge/?version=latest
   :target: https://escrutinio-social.readthedocs.io/es/latest/?badge=latest
   :alt: Documentation Status



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
