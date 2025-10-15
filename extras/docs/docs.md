# Escribir documentación

Le damos total relevancia a la documentación de Escrutinio Social.
Es un sistema complejo y requiere detalles tanto para su uso, configuración, administración en condiciones de "misión crítica" y
desarrollo.

Utilizamos el software Sphinx y podés escribir nuevos capitulos tanto en markdown como en restructuredText. Para eso creá tu archivo en
la carpeta `docs/` y declaralo en alguna directiva `..toctree::`,
por ejemplo en los indices principales de `docs/index.rst`


Usamos el servicio [Read the Docs](https://readthedocs.org/)
para compilar automaticamente y tener al día la documentación en
https://escrutinio-social.readthedocs.io/

En cada *pull request* genera una compilación de la documentación
sobre ese branch para cersiorarse de que no hay errores antes de mergear. Por favor, revisá el resultado, especialmente si cambiaste algo.

También podes compilar la documentación localmente

```bash
$ pip install -r requirements/docs.txt
$ cd docs/
$ make html
$ xdg-open _build/html/index.html
```


## Diagrama de modelos

En cada compilación, se incluye {ref}`un diagrama <modelos>` de la definición de los modelos principales.
Esto se realiza ejecutando `make update-models-diagram` al inicio de la compilación, que utiliza a su vez un [comando de django-extensions](https://django-extensions.readthedocs.io/en/latest/graph_models.html) para crear la imágen inspeccionando el código.




