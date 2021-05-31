
# A. Para comenzar de cero con la base 
Ejecutar los comandos::
```
  $ make down
  $ make build
  $ make setup-dev-data
  $ make shell-app
```
el último comando nos lleva al shell de la app, desde donde ejecutaremos el resto de los comandos
```
  # python manage.py createcachetable
```

# B. Pasos para cargar DISTRITOS, SECCIONES, CIRCUITOS, ESCUELAS Y MESAS

1) Borrar el distrito de prueba de la BD a través del admin de la app.
Con eso borramos todos los datos de prueba, secciones, circuitos, mesas y resultados inclusive. 

2) Crear todos las categorías de distribución geográfica de las mesas: Distritos, Secciones y Circuitos
```
  # ./manage.py importar_circuitos <path>/circuitos.csv
```

Formato del archivo:

*circuito_nro,circuito_name,seccion_nro,seccion_name,distrito_nro,distrito_name*

3) Crear todos los lugares de votación
  ```
  # ./manage.py importar_escuelas <path>/escuelas.csv
  ```

  Formato del archivo:
  
  *escuela_nro,distrito_nro,seccion_nro,circuito_nro,escuela,direccion,localidad,latitud,longitud*

4) Crear mesas
  ```
  # ./manage.py importar_mesas <path>/mesas.csv
  ```
  
  Formato del archivo:
  
  *mesa,circuito,lugar_votacion,seccion,distrito,electores*

  **Pendiente** Entiendo que se puede usar la misma función para setear los electores, pero no lo probé. 

  **Aclaración**: La diferenica con el comando importar_escuelas_y_mesas es el formato. Este último comando pide para cada escuela "desde-hasta" indicando nro de mesa de cada escuela.


# C. Para configurar categorías electorales y opciones

**Categorías Generales** indica qué se vota en una determinada elección. Por ejemplo, Diputados Nacionales, Presidente, etc

**Categorías** relaciona las categorías generales con los lugares geográficos en los que se vota. Por ejemplo, Presidente se vota en todo el país, pero Diputados Nacionales, tiene candidatos diferenciados en cada provincia, por lo tanto una categorías sería Diputados Nacionales por Córdoba.

**Partidos** nos permite una clasificación más general de las opciones. Es muy útil para cuando hay varias opciones para un mismo partido. 

**Opciones** las opciones "Positivas" son las correspondientes a cada partido, también se almacena entre las opciones los votos en blanco, votos impugnados, votos nulos y la metadata, cantidad de electores y de votantes.

1. Desde el admin de la app  
  - Borrar todas las "categorías generales" de la base
  - Borrar todos los partidos de la base. 
  - Borrar todas las opciones de la base. 

2. Crear las categorías generales 

  La categoría "Presidente y vice" debe tener slug "PV". Si se quiere cambiar el slug, es necesario cambiar la configuración. 
  ```
    # ./manage.py importar_categorias_generales <path>/categorias_generales.csv
  ```
  Formato del archivo:
  
  *nombre,slug*


3. Asociar la categoría general creada a la Eleccion en el admin de la app

  **Pendiente**
    - habría que ver si hace falta o lo puede hacer el script. 


4. Crear las categorías que se votan. A su vez, asociar a las mesas en las que se vota cada categoría.

  ```
    # ./manage.py importar_categorias <path>/categorias.csv  
  ```
    
5. Asociar las categorías creadas a Eleccion en el admin

  **Pendiente**
    - habría que ver si hace falta o lo puede hacer el script. 

6. Crear las opciones partidarias y asociarlas a las categorías correspondientes.
  ```
    # ./manage.py importar_opciones <path>/opciones.csv
  ```
    
7. Crear blancos, nulos, etc. y los asociarlos a todas las categorías.
  ```
    # ./manage.py setup_opciones_basicas
  ```
    

# D. Quedan algunos comentarios mas de configuracion que se podrían revisar en 
 https://github.com/EscrutinioSocial/escrutinio-social/wiki/Importaci%C3%B3n-de-datos-y-deploy

 o en la wiki original escrutinio/escrutinio-paralelo/wikis/importación-datos-general-2019
