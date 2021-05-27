La funcionalidad *antitrolling*
********************************

Objetivo
########

El sistema puede ser usado por cualquiera que obtenga credenciales. Si alguna persona, o grupo de personas lo quisiera usar de forma maliciosa, entonces el sistema lo debe detectar y bloquear.

Entendemos que hay casos en los que las personas (sin intención de maldad) cargan mal algún resultado, por ejemplo en ciertos casos que la letra no es legible. Estos casos igual los queremos marcar como dudosos porque si la persona tiene muchas pequeñas fallas entonces puede causar que la carga de resultados nunca converja.

El mecanismo entonces, detecta a quienes intencional o no, cargan los resultados de forma incorrecta.

Las personas en el sistema son `fiscales`, al marcarlos como *troll* lo invalidamos, y se invalidan **todas** las cargas anteriores.


Scoring
#######

Hay distintas métricas que el sistema de detección de trolls tiene en cuenta. La configuración de dichas métricas se encuentra en el archivo de `settings.py`:

    # Valor de scoring que debe superar un fiscal para que la aplicación lo considere troll
    SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL = 500
    # Cuanto aumenta el scoring de troll por una identificacion distinta a la confirmada
    SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA = 200
    # Cuanto aumenta el scoring de troll por poner "problema" en una MesaCategoria para la que se confirmaron cargas
    SCORING_TROLL_PROBLEMA_MESA_CATEGORIA_CON_CARGA_CONFIRMADA = 200

El primer valor es el umbral que se usará para marcar a una fiscal como troll. Esto se puede configurar si detectamos que durante la carga se nos escapan fiscales o estamos siendo muy crueles.

Por otro lado si una mesa se encuentra identificada por dos fiscales y una tercera la carga mal, entonces se le suman 200 puntos por error de cargar mal el dato de la mesa. En esta categoría están por ejemplo, el número de mesa, sección, distrito, etc.

El tercer parámetro es para evitar que marquen las fotos de las actas con problema cuando en realidad otras fiscales le cargan datos y estos son confirmados. Entendemos que puede haber fotos mal subidas, pero si dos otras fiscales la pueden leer y cargar, entonces restamos puntos a quien esta queriendo arruinar fotos que se ven bien.

Se puede consultar el puntaje de un `fiscal` mediante el método: `scoring_troll()`.

Desde la web se pueden admisnitrar los fiscales, y marcarlos o desmarcarlos.


¿Cuánto pesan las cargas?
************************

Si un acta tiene dos cargas coincidentes y una tercera que difiere, entonces al fiscal que cargo alguna categoría (o todas) mal, se le suma la diferencia de votos a modo de penalización.

Por ejemplo, si para presidente dos cargas coinciden en 40 votos y un tercer fiscal carga 30, entonces a ese tercer fiscal se le suman 10 puntos a su nivel de troll.



Invalidación de cargas
######################
Al detectar a un fiscal como troll, todas sus cargas anteriores se invalidan: `Carga.objects.filter(invalidada=True)`.

Cuando se corra el comando asincrónico: `consolidar_identificaciones_y_cargas.py` se revisarán y cambiarán:
* Cargas: los valores cargados de votos
* Identificaciones: la identificación de mesa del acta

En el caso de las categorias, en el objeto: `MesaCategoria`, se puede ver que el **STATUS** puede degradarse de *consolidada_dc* a *sin_consolidar* o *sin_cargar*. Dependiendo el nivel de daño que haya hecho el fiscal.

La idea es que si un acta tiene una carga realizada por un fiscal que ahora es troll, entonces no podemos confiar en la doble carga que realizó. El sistema le enviará el acta a otro fiscal para que pueda volver a cargarla.

En el caso de las identificaciones, pueden pasar a no estar procesadas y esa identificacion ser invalida. En ese caso, también necesitamos que otro fiscal constate con una segunda carga los datos de identificación de la mesa.


Qué ve el Troll
###############
Lo lindo es que nuestros trolls, seguirán jugando con el sistema y sus acciones no impactarán en nuestros resultados. No se les avisará que fueron degradados de fiscales a trolls.