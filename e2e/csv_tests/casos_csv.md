Casos
======= 

Datos:

Codigos de listas:
FdT es 136, JpC 135 y C2019 137.

1. Validaciones generales de estructura del archivo
--------------------------------------------------------------

1. ~~Nombre de archivo demasiado largo~~
2. ~~Nombre de archivo con caracteres latinos (tildes eñes, etc)~~
3. ~~Archivo sin header~~
4. ~~Archivo con header y columnas faltantes~~
5. ~~Carga de datos alfanumericos en cualquiera de las columnas~~

2. Validaciones de carga Distrito seccion circuito mesa y lista
--------------------------------------------------------------

1. Dos registros con identico Distrito, Seccion, circuito, mesa y lista.
1. Seccion, circuito, mesa y lista ok pero no Distrito
1. Distrito, Circuito, mesa y lista ok pero no Secccion
1. Distrito, seccion, Circuito y lista ok pero no mesa.
1. Distrito, Seccion, circuito y mesa ok pero no lista.
1. Distrito, Seccion, lista y mesa ok pero no circuito .


3. Validaciones de carga no OK
------------------------------------------------------------

1. ~~Para mismo Distrito, Seccion, circuito y  mesa, cargar dos registros para
   misma lista cuya suma sea mayor a la cantidad de electores.~~
2. ~~Para mismo Distrito, Seccion, circuito y  mesa, cargar dos registros para
   distinta lista cuya suma sea mayor a la cantidad de electores.~~


4. Validaciones de carga OK
------------------------------------------------------------

1. ~~Para mismo Distrito, Seccion, circuito y  mesa, cargar dos registros para
   distinta lista cuya suma sea igual a la cantidad de electores. Para presidente~~

1. ~~Para mismo Distrito, Seccion, circuito y  mesa, cargar dos registros para
   distinta lista cuya suma sea igual a la cantidad de electores. Para Gov~~

1. ~~Para mismo Distrito, Seccion, circuito y  mesa, cargar dos registros para
   distinta lista cuya suma sea igual a la cantidad de electores. Para Diputado~~

