Historia
========
En el año 2013, durante las elecciones legislativas, el escrutinio provisorio resultó llamativo en la provincia de Córdoba, Argentina, ya que estuvio en disputa el resultado de la categoría Diputado/a Nacional: el partido minoritario parecía haber obtenido el resultado para obtener  representación parlamentaria por primera vez, pero en un momento de la noche el resultado cambió y fue finalmente la Unión Cívica Radical ( primera fuerza de aquella elección) la que se llevó esa banca.

Fue tal la polémica y tan estrecho el márgen que Martín Gaitán, a la postre uno de los creadores de Escrutinio Social, hizo un llamamiento `desde su weblog <http://mgaitan.github.io/posts/no-al-fraude-en-cordoba-ayudanos/>`_ para revisar "cargas sospechosas" del escrutinio provisorio.

Para esto obtuvo primero mediante un pequeño software (un "scraper") todas las imágenes y la carga de datos oficial correspondiente a cada telegrama. Aplicando algunas inferencias estadísticas básicas (por ejemplo, es sospechoso que el resultado en una mesa para un partido sea muy distinto que el promedio en las demas mesas en esa escuela o circuito), obtuvo listas de actas cuya carga era plausible de contener errores y debía ser revisada.

Pronto ese trabajo se viralizó y si bien finalmente no hubo modificaciones en los resultados, fue el puntapie inicial para diferentes iniciativas relacionadas a la transparencia electoral.

A finales de ese mismo año, un grupo de investigadores de la Facultad
de Matemática, Física, Astronomía e Informática (FaMAF) de la Universidad Nacional de Córdoba propuso realizar una "hackatón" enfocada en la temática electoral que continuara y potenciara la idea germinal. Ese encuentro se llamó "Democracia con Códigos" y fue donde se discutieron y escribieron las primeras lineas de código de lo que sería "Escrutinio Social". La idea era profesionalizar y sistematizar la carga de datos de voluntaries (superar el "formulario de Google" del *post* original) y lograr que la detección de anomalías se haga más automática. En ese mismo encuentro se conocieron los fundadores (y de alguna manera dió origen) de la ONG Open Data Córdoba (ODC).

En 2017, durante otras elecciones legislativas nacionales, el Frente Córdoba Ciudadana (representación de Unidad Ciudadana, el partido fundado por Cristina Fernández de Kirchner, en la provincia de Córdoba) llevó a `Pablo Carro <https://pablocarro.com.ar/>`_ como candidato a diputado nacional (que resultaría finalmente electo). El equipo de campaña necesitaba un software para su escrutinio interno y se recuperaron las ideas y bases de aquella hackatón, que eran de código abierto, y se lo llevó a un estado funcional. Ese software se llamó "`Carreros <https://github.com/concristina/carreros>`_". Además del sistema de escrutinio paralelo, incluía muchas otras funcionalidades para la optimización de la campaña y el operativo electoral. 

Para ODC la transparencia electoral siempre fue parte principal de su agenda y fueron quienes se tomaron el trabajo de "extraer" de Carreros la parte estrictamente relacionada al escrutinio, volviendo a publicarlo bajo su nombre original.

El éxito de las experiencias en Córdoba permitió que el mismo software sea la base para el que se usaría en operativo electoral a nivel nacional durante las elecciones presidenciales del año 2019 del Frente de Todos, que llevó a la presidencia a Alberto Fernández. Muchísimas funcionalidades tendientes a la escala (doble carga, antitrolling, optimizaciones varias) fueron agregadas durante esta etapa, con un equipo conformodo por voluntarios de distintas agrupaciones políticas que apoyaban a esta formula. 

Pasadas las elecciones, el software se liberó nuevamente adoptando ya el estatus de un proyecto de código abierto independiente (bajo la "organización" https://github.com/EscrutinioSocial), que tiene el afán de ser usado en elecciones de cualquier nivel en diversos lugares del mundo.


.. [#] Las bancas se reparten por sistema D'Hont
