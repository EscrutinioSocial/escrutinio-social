# Cómo Contribuir #

Coordinamos las actividades a través de un canal de Telegram. Podés
ponerte en contacto con @AraCba para pedir acceso.

Trabajamos en un repositorio privado
(https://gitlab.e-va.red/escrutinio/) contra el branch develop.

Por el momento no hay integración continua con Travis y con eso
perdemos coverage testing, documentación, etc. (pero ver
https://t.me/c/1156246225/198)

Hasta tanto esté resuelto eso, cada quien se compromete a probar
localmente y mantener (o preferentemente subir) la cobertura.

Los merge-request (MR, aka PR) los abrimos contra develop y en master
taggearemos releases que se definan en milestones.

Se agradece respetar pep8/pyflake (https://pypi.org/project/flake8/),
es tan simple como instalar flake8 y ejecutarlo desde el root del repo:
```
$ flake8
```

## Repositorio Original ##

Este repositorio es un fork de [escrutinio-social](https://github.com/OpenDataCordoba/escrutinio-social "Escrutinio Social") 
de [Open Data Córdoba](https://www.opendatacordoba.org/).
