# Visualizaciones

## Para generar las visualizaciones estáticas hacer:
```
$ make collectstatic
$ make crawl-resultados tipoDeAgregacion=todas_las_cargas opcionaConsiderar=prioritarias
```
Se pueden pasar por parámetro los distintos tipos de agregación y opciones a considerar.

## Para ver las visualizaciones:
```
$ make crawl-resultados-up
```
y navegar a: http://localhost:8080/crawl-resultados/elecciones/resultados/1.html

## Para deployar las visualizaciones en S3:
* copiar la carpeta static
* copiar la carpeta crawl-resultados
* habilitar cors (para que pueda cargar las fonts): https://docs.aws.amazon.com/AmazonS3/latest/dev/cors.html
