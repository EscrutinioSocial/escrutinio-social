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


# Guía de estilo


La intención de tener una guía de estilo de codificación es lograr una consistencia
que facilite la lectura y la comprensión del proyecto.

No nos limitamos a las minucias del formato, sino a fomentar la adopción de
aquellos *idioms* que hacen que nuestro código resulte "pythónico" (y "djangoso" (?)),
asumiendo las convenciones más comunes de la comunidad en general, y

    “A language that doesn’t affect the way you think about programming, is not worth knowing.”
    – Alan Perlis

Por supuesto, también fomentamos e intetamos aplicar las buenas prácticas del desarrollo de software
que son agnósticas del lenguaje.


### Algunas notas iniciales

- Esta guía de estilo es un `pep8.upgrade(esta_guia)`. Es decir, siempre que no estén especificadas,
  valen las recomendaciones de la guía de estilo oficial de Python. Y algunas que están aqui,
  actualizan o modifican las de [PEP8](http://pep8.org).

- No queremos ser "nazis del formato". Justamente la intención de tener esto es ganar tiempo y confort
  en el desarrollo, y si esa búsqueda nos obliga a lo contrario, pierde su sentido.

  Es válido pedir o recomendar cambios de formato en una revisión de
  código, pero no queremos bloquear una integración porque alguien dejó un espacio de menos o de más.

- Aceptamos usar herramientas de "autoformateado" como `yapf`, `black`, `isort`, o las que ofrezca tu editor
  preferido si considerás que te ahorran trabajo, pero siempre respetando las convenciones del proyecto.

  Usalas siempre sobre bloques de código específicos y no de manera automática sobre todo un módulo.

- Esta guía no está escrita en piedra y puede cambiar cuando la experiencia o los gustos del equipo lo dicten.
  Para proponer cambios, aplicaran los mismos criterios y herramientas que para el código: enviar un MR/PR
  y obtener los votos necesarios para su integración!


### Convenciones


- El ancho máximo de linea recomendado es de 109 caracteres.
  (79 es demasiado poco para nuestro gusto por los nombres de variables expresivos)

- Nombres

  - de clases en `CamelCase`
  - de constantes en `UPPERCASE`
  - todo el resto (variables, funciones, argumentos, módulos, etc.), en `snake_case`

- Imports

  - Como recomienda PEP8, nunca hacer `from bla import *`.
  - Si la lista de objetos a importar de un determinado namespace realmente es muy grande,
    o sabemos que va a cambiar mucho, se puede importar el namespace.
    El ejemplo típico es `django.db.models` que contiene un montón de objetos usados
    en la definición de modelos

    ```
    from django.db import models

    class Foo(models.Model):
       campo = models.BooleanField ...
    ```

  - Si el espacio de nombre a importar es muy largo o puede colisionar con otro, usar un alias


 - Si entran en el ancho máximo, hacer los imports en la misma línea. Si no entran, preferir un
   formato de sangrado vertical en orden alfabético

    ```
    from namespace import (
       bar,
       foo,
       ...,
    )
    ```

   No olvidar la coma en el último elemento, así el "diff" es menos verborrágico cuando la
   se agregue una nueva línea.


 - El orden los imports es por procedencia y luego alfabeticamente.

    ```
    <imports de la stdlibs>
    ...

    <imports de requerimientos>
    ....

    <imports del proyecto>
    ....


- Strings

  - Para strings cortos. preferimos comilla simple (apóstrofes) sobre comillas doble, salvo,
    obviamente, que se necesiten apóstrofes dentro del texto.
  - Para strings multilínea  triple comilla doble, dejando las comillas
    solas en la primera y última línea siempre que se pueda
  - Excepción con los docstrings, que preferimos aplicar la regla anterior de triple comilla
    aunque sean de una sola

    ```
        """
        Esta función recibe ``foo``
        """
    ```
  - Preferimos f-strings por sobre otro tipo de interpolación. Pero la lógica "dentro" del
    f-string debe ser mínima, haciendo los precómputos necesarios.
  - No nos gustan los backslashes. Si el texto es multilinea, usar comillas triples
    Si un texto es excepcionalmente largo, envolverlo en paréntesis

    ```
    (
      "esto es un solo string "
      "repartido en muchas lineas"
    )
    ```

- Docstrings

    - Nos gustan y sirven. Pero deben referirse a funcionalidad y no a explicar la implementación
      Para eso están los comentarios... y el código en sí .
    - Pueden formatearse en restructuredText, para que Sphinx los muestre bonitos.

- Objetos grandes

  - Aplica el mismo criterio de identación vertical de los imports

   ```
   una_lista_larga = [
       'item1',
       'item2',
       [
           'item_de_item3',
           ...,
       ],
       ...,
   ]
   ```

   - Mismo crierio para diccionarios y otras estructuras de datos.


- Condiciones

  - No nos gustan los backslashes, preferimos envolver en paréntesis.

  - No nos gustan los paréntesis salvo que sean necesarios.

  - Cuando hay múltiples condiciones que requieren varias lineas y
    el costo de evaluación es despreciable, preferimos precalcular
    en variables que aporten semántica

    ```
    requiere_parcial = self.mc.categoria.requiere_cargas_parciales
    sin_consolidar = self.mc.status[:2] < MesaCategoria.STATUS.parcial_consolidada_dc[:2])
    if requiere_parcial and con_status:

    ```
    Cuando la mera evaluación puede ser costosa computacionalmente, no hacer esto
    así usufructuamos los "[cortocircuitos](https://docs.python.org/3/library/stdtypes.html#boolean-operations-and-or-not)" del `if`

  - La estructura ternaria (foo = 'bar' if condicion else 'baz') es útil siempre que la condicion no deba reusarse
    y todo entre en el ancho. En caso contrario

  - Usar `foo is not bar` en vez de `not (for is bar)`

  - En caso de que inevitablemente una condición se compone de muchas condiciones parciales
    en varias lineas, preferir

- Funciones

  - No usar lambdas asignados a un nombre de variable. Definir con `def` en ese caso.
  - No nos gustan `map` y `filter`, preferimos comprenhensions. Especialmente si son
    generator expressions.

  - Sospechamos de los bloques de código que no entran en una pantalla
    Si una función se torna demasiado grande, preferimos factorizar pequeñas
    funciones auxiliares (que eventualmente pueden definirse de manera anidada
    para reutilizar definiciones del contexto).

- [YAGNI](https://en.wikipedia.org/wiki/YAGNI)

  - Evitamos la tentación de escribir o mantener código que no sirve pero "podemos llegar a necesitar".
    Borramos en vez de comentar código, con un commit prolijo acotado a ese fin y un claro
    mensaje, referencias en el issue tracker en los tickets relacionados, y otras maneras de
    dejar pistas si eventualmente hay que encontrar

  - El mismo criterio debería aplicarse a tests "skipeados". Salvo que sea evidente
    que alguien está trabajando sobre la funcionalidad relacionada a esos tests,
    si hay tests que no sirven (ni pasan) en el estado actual del proyecto, no deberian dejarse
    en el código.

- Django templates

  - Nos gusta dejar sangria de dos espacios para enfatizar los bloques.
    Es decir, que las etiquetas de django "sobresalgan" hacia la izquierda un toque.

     ```

      {% if incluir_votos %}
        <td id="votos_{{ partido.id|default:partido|lower }}" class="dato">{{ fila.votos }}</td>
      {% endif %}
      ...
     ```

   - Priorizar la legibilidad del template por sobre la del código (html o lo que sea) resultante.
     Por ejemplo, frecuentemente comentamos usando etiquetas de template en vez de etiquetas de html.
   - Siempre que aplique, usamos las mismas convenciones que para Python


- Querysets

    - En algunas APIs, como los queryset de django, es posible y útil "encadenar" llamadas a métodos.
    Las reglas de sangrado vertical aplican aqui.

    ```
    query = qs.values(
        'mesa', 'status'
    .annotate(
        total=Count('status')
    ).annotate(
        cuantos_csv=cuantos_csv
    )
    ```

    - Cuando las condiciones de filtrado son abundantes o dinámicas, se pueden definir
      con antelación utilizando diccionarios y/u objetos tipo `Q`



## Repositorio Original ##

Este repositorio es un fork de [escrutinio-social](https://github.com/OpenDataCordoba/escrutinio-social "Escrutinio Social")
de [Open Data Córdoba](https://www.opendatacordoba.org/).


