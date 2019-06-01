Escrutinio Social
=================

Escrutinio Social es una plataforma web para la realización de un escrutinio provisorio y auditoría
ciudadana a partir de fotos documentos aportados por fiscales partidarios. 

Está basada en el framework Django, y un stack de tecnologías libres. 

Licencia BSD 

Sumate a la `sala de chat del proyecto <https://join.slack.com/t/opendatacba/shared_invite/enQtNjQ4OTY5MTg3Nzk2LTgxMDU5NTY1MWNmZTdkMzVmM2EyNmUwZGQ0Nzg0ZjdlNjBkZmI0Zjc2MTllMWZhZjAzMTEwMjAwYzk3NGNlMzk>`__


Datos
-----

Proceso de carga de datos para comenzar

.. code-block:: bash

    # traer las secciones, circuitos, escuelas y mesas
    ./manage.py importar_carta_marina_2019_gobernador

    # traer datos de las mesas
    ./manage.py importar_mesas_2019_gobernador

    # Traer los partidos que participan con el orden de las actas
    ./manage.py importar_partidos_cba_2019

    # Crear las opciones para la carga de datos
    ./manage.py crear_opciones_elecciones

    # darle colores diferenciados a la planilla de carga de datos
    ./manage.py colorize_elecciones

    # Crear (por ejemplo) 5 usuarios para los data entries del bunker
    ./manage.py generar_accesos_data_entries --equipo=BUNKER --cantidad=5 

    # Importar mesas testigo
    ./manage.py importar_mesas_testigo_2019

Instalación
-----------

Ver [Instalación](https://github.com/eamanu/escrutinio-social/tree/add-installation/install/README.md)
