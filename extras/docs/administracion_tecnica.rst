Guía de administración técnica
==============================


Importación de datos para una elección
--------------------------------------


.. toctree::

   configuracion.md


Comandos útiles
---------------


Importar datos desde email
++++++++++++++++++++++++++


El comando ``importar_actas_desde_email`` permite conectarse a una o más cuentas IMAP
para bajar correos electrónicos y convertir sus archivos adjuntos en imágenes a clasificar.

Cada email puede tener una o más imágenes adjuntas.

Para esto es necesario configurar la variable de entorno ``IMAPS`` como un string json que contiene una lista de diccionarios con los datos de las cuentas.

Por ejemplo:


.. code-block::

    IMAPS=[{"email": "email_de_actas@gmail.com", "host": "imap.gmail.com", "user": "email_de_actas@gmail.com", "pass": "xxxx", "mailbox": "INBOX"}]

Luego

.. code-block::

    $ python manage.py -v 3 --include-seen --only-images importar_actas_desde_email


Vea ``python manage.py importar_actas_desde_email --help`` para una ayuda sobre las opciones.



