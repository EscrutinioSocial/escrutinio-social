
./manage.py clean_all

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