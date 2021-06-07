"""
Django settings for escrutinio_social project.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import json
import os
import sys
from model_utils import Choices
import logging.config
import structlog

from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', "random key")
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
DEBUG = os.getenv('DEBUG') == "True"
TESTING = os.path.basename(sys.argv[0]) == "pytest" or os.getenv("READTHEDOCS")

# Application definition

INSTALLED_APPS = [
    'custom_templates',  # our hack to override templates
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'django_exportable_admin',
    'anymail',
    'localflavor',
    'django_extensions',
    'fancy_cache',
    'material.theme.lightblue',
    'material',
    'dbbackup',
    'constance',
    'constance.backends.database',
    'djangoql',
    'django_summernote',

    # 'material.admin',
    # 'django.contrib.admin',
    'material.frontend',
    'django_admin_row_actions',
    'hijack',
    'compat',
    # 'attachments',
    'djgeojson',
    'leaflet',
    'versatileimagefield',
    'darkroom',

    # django-rest-framework
    'rest_framework',
    'drf_yasg',

    # django-autocomplete-light
    'dal',
    'dal_select2',

    # django-storages
    'storages',

    # nuestras apps,
    'background',
    'fiscales.apps.FiscalesAppConfig',  # Hay que ponerlo así para que cargue el app_ready()
    'elecciones.apps.EleccionesAppConfig',
    'adjuntos',
    'problemas',
    'contacto',
    'api',
    'antitrolling',
    'scheduling',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'fiscales.middleware.OneSessionPerUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_structlog.middlewares.RequestMiddleware',
]

ROOT_URLCONF = 'escrutinio_social.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'constance.context_processors.config',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'elecciones.context_processors.version',
            ],
        },
    },
]

WSGI_APPLICATION = 'escrutinio_social.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

# Si se instala localmente crear un archivo .env
#
# DB_NAME=db_name
# DB_USER=postgres
# DB_PASS=changeme
# DB_HOST=db
# DB_PORT=port

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', ''),
        'TEST': {"NAME": "travis_ci_test"} if "TRAVIS" in os.environ else {},
    }
}
# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'America/Argentina/Cordoba'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

if DEBUG or TESTING:
    STATICFILES_FINDERS = [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    ]

    STATIC_URL = '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')

    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
else:
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_DEFAULT_ACL = 'public-read'

    STATICFILES_AWS_LOCATION = 'static'
    STATICFILES_STORAGE = 'escrutinio_social.storages.StaticStorage'

    STATIC_URL = '{}/{}/'.format(AWS_S3_ENDPOINT_URL, STATICFILES_AWS_LOCATION)
    STATIC_ROOT = 'static/'

    MEDIAFILES_AWS_LOCATION = 'media'
    DEFAULT_FILE_STORAGE = 'escrutinio_social.storages.MediaStorage'

    MEDIA_URL = '{}/{}/'.format(AWS_S3_ENDPOINT_URL, MEDIAFILES_AWS_LOCATION)
    MEDIA_ROOT = 'media/'


DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

DBBACKUP_STORAGE = 'django.core.files.storage.FileSystemStorage'
DBBACKUP_STORAGE_OPTIONS = {'location': os.path.join(BASE_DIR, 'backups')}

HIJACK_LOGIN_REDIRECT_URL = 'home'  # Where admins are redirected to after hijacking a user
HIJACK_ALLOW_GET_REQUESTS = True
HIJACK_LOGOUT_REDIRECT_URL = 'admin:fiscales_fiscal_changelist'

LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (-31.418293, -64.179238),
    'DEFAULT_ZOOM': 8,
    'MIN_ZOOM': 4,
    'MAX_ZOOM': 18,
    'PLUGINS': {
        'awesome-markers': {
            'css': [
                'https://cdn.rawgit.com/lvoogdt/Leaflet.awesome-markers/2.0/develop/dist/leaflet.awesome-markers.css'
            ],
            'js':
                'https://cdn.rawgit.com/lvoogdt/Leaflet.awesome-markers/2.0/develop/dist/leaflet.awesome-markers.min.js',
            'auto-include': True,
        },
    }
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated', ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication'
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

SWAGGER_SETTINGS = {
    'PERSIST_AUTH': True,
    'DEFAULT_INFO': 'api.urls.swagger_info',
    'SECURITY_DEFINITIONS': {
        'Basic': {
            'type': 'basic'
        },
        'Bearer': {
            'in': 'header',
            'name': 'Authorization',
            'type': 'apiKey',
        }
    }
}

ANYMAIL = {
    # (exact settings here depend on your ESP...)
    "MAILGUN_API_KEY": "",
    "MAILGUN_SENDER_DOMAIN": '',  # your Mailgun domain, if needepd
}
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGGING_CONFIG = None

LOGLEVEL = os.getenv('DJANGO_LOGLEVEL', 'info').upper()

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s [%(name)s:%(lineno)s] %(module)s %(process)d %(thread)d %(message)s",
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
        "plain_console": {
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
        },
    },
    "loggers": {
        "consolidador": {
            "handlers": ["plain_console"],
            "level": "DEBUG",
        },
        "csv_import": {
            "handlers": ["plain_console"],
            "level": "DEBUG",
        },
        "scheduler": {
            "handlers": ["plain_console"],
            "level": "DEBUG",
        },
        "": {
            "handlers": ["console"],
            "level": LOGLEVEL,
        },
        "django_structlog": {
            "handlers": ["plain_console"],
            "level": LOGLEVEL,
        },
    }
})

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.ExceptionPrettyPrinter(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


# EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"  # or sendgrid.EmailBackend, or...
DEFAULT_FROM_EMAIL = "algo@email.com"  # if you don't already have this in settings
DEFAULT_CEL_CALL = '+54 9 351 XXXXXX'
DEFAULT_CEL_LOCAL = '0351 15 XXXXX'

FULL_SITE_URL = 'https://this-site.com'

CACHES = {
    'dbcache': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'elecciones_cache',
    },
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# config para el comando importar_actas
IMAPS = json.loads(os.getenv("IMAPS", "[]"))


SUMMERNOTE_THEME = 'lite'
SUMMERNOTE_CONFIG = {
    # You can disable attachment feature.
    'disable_attachment': True,
}


# contacto settings
CARACTERISTICA_TELEFONO_DEFAULT = '351'  # CORDOBA
CARACTERISTICA_DEFAULT = '351'

# Por defecto no se muestra gráfico en la página de resultados.
SHOW_PLOT = False

MIN_COINCIDENCIAS_IDENTIFICACION = 1
MIN_COINCIDENCIAS_CARGAS = 1
MIN_COINCIDENCIAS_IDENTIFICACION_PROBLEMA = 1
MIN_COINCIDENCIAS_CARGAS_PROBLEMA = 1

# Tiempo máximo luego del cual se considera que un fiscal no cumplió con la tarea que tenía asignada y
# le es entregada a otra persona.
TIMEOUT_TAREAS = 3  # En minutos

# Tamaño maximo de archivos permitidos en el formulario
# de subida de fotos y CSV
MAX_UPLOAD_SIZE = 12 * 1024 ** 2     # 12 Mb

# Tiempo en segundos que se espera entre
# recálculo de consolidaciones de identificación y carga
PAUSA_CONSOLIDACION = 15
# Cuánto tiempo esperar para considerar que una carga o idenfificación que tomó el consolidador, está libre.
# En minutos.
TIMEOUT_CONSOLIDACION = 5

# Prioridades standard, a usar si no se definen prioridades específicas
# para una categoría o circuito
PRIORIDADES_STANDARD_SECCION = [
    {'desde_proporcion': 0, 'hasta_proporcion': 2, 'prioridad': 4},
    {'desde_proporcion': 2, 'hasta_proporcion': 10, 'prioridad': 40},
    {'desde_proporcion': 10, 'hasta_proporcion': 100, 'prioridad': 200},
]
PRIORIDADES_STANDARD_CATEGORIA = [
    {'desde_proporcion': 0, 'hasta_proporcion': 100, 'prioridad': 100},
]

# Las siguientes constantes definen los criterios de filtro
# para obtener aquellas instancias que se utilizan en el cálculo de resultados
# o en validaciones de carga, etc.
# Por ejemplo:
#
# blanco = Opcion.objects.get(**OPCION_BLANCOS)
OPCION_BLANCOS = {'tipo': 'no_positivo', 'nombre_corto': 'blanco', 'partido': None, 'codigo': '10000'}
OPCION_NULOS = {'tipo': 'no_positivo', 'nombre_corto': 'nulos', 'partido': None, 'codigo': '10001'}
OPCION_TOTAL_VOTOS = {'tipo': 'metadata', 'nombre_corto': 'total_votos', 'partido': None, 'codigo': '10010'}
# Las que siguen son la metadata optativa, es decir, la metadata que recolectamos de los que nos mandan
# por CSV (si lo mandan), pero que no le queremos pedir al usuario.
OPCION_TOTAL_SOBRES = {
    'tipo': 'metadata_optativa', 'nombre_corto': 'sobres', 'partido': None, 'codigo': '10011'
}
OPCION_RECURRIDOS = {
    'tipo': 'metadata_optativa', 'nombre_corto': 'recurridos', 'partido': None, 'codigo': '10002'
}
OPCION_ID_IMPUGNADA = {
    'tipo': 'metadata_optativa', 'nombre_corto': 'id_impugnada', 'partido': None, 'codigo': '10003'
}
OPCION_COMANDO_ELECTORAL = {
    'tipo': 'metadata_optativa', 'nombre_corto': 'comando_electoral', 'partido': None, 'codigo': '10004'
}

KEY_VOTOS_POSITIVOS = 'votos_positivos'

SLUG_CATEGORIA_PRESI_Y_VICE = 'PV'
SLUG_CATEGORIA_GOB_Y_VICE_PBA = 'GB_PBA'

URL_ARCHIVO_IMPORTAR_CORREO = {}
URL_ARCHIVO_IMPORTAR_CORREO[SLUG_CATEGORIA_PRESI_Y_VICE] = 'https://sheets.googleapis.com/v4/spreadsheets/1hnn-BCqilu2jXZ-lcNiwhDa_V-QTCSp-EMqhpz4y2fA/values/A:XX'
URL_ARCHIVO_IMPORTAR_CORREO[SLUG_CATEGORIA_GOB_Y_VICE_PBA] = 'https://sheets.googleapis.com/v4/spreadsheets/10GW6KVlORVor9HRbhmr9EtzuYEqlFD7mJmxyNG7LQCs/values/A:XX'

# Código de partidos principales para validaciones.
CODIGO_PARTIDO_NOSOTROS = '136'
CODIGO_PARTIDO_ELLOS = '135'
CODIGO_PARTIDO_NOSOTROS_BA = '136'
CODIGO_PARTIDO_ELLOS_BA = '135'

# Número del Distrito Provincia de Buenos Aires
DISTRITO_PBA = '2'

# Cada cuánto tiempo actualizar el campo last_seen de un Fiscal.
LAST_SEEN_UPDATE_INTERVAL = 2 * 60  # en segundos.

# Cuándo expira una sesión.
SESSION_TIMEOUT = 5 * 60  # en segundos.

# Flag para decidir si las categorias pertenecientes a totales de los CSV tienen que estar completas
# Ver csv_import.py
OPCIONES_CARGAS_TOTALES_COMPLETAS = True

# Opción para elegir ninguna proyección en el combo
SIN_PROYECCION = ('sin_proyeccion', 'Sólo escrutado')

# Opción para indicar que no se debe mostrar información relacionada con cantidad de electores por mesa / escuela / etc
# una razón para esto es que su no se cuenta con información fidedigna al respecto
OCULTAR_CANTIDADES_DE_ELECTORES = True

# Constantes para configurar el modo de visualización de los porcentajes de votos
# de cada partido, habiendo dos opciones:
# El porcentaje de votos se calcula sobre el total de votos afirmativos y en
# blanco.
ME_OPCION_PASO = 'PASO'
# El porcentaje de votos se calcula sobre el total de votos afirmativos.
ME_OPCION_GEN = 'GENERALES'

# Seteamos el modo de elección; la manera en que visualización de porcentajes de
# votos de la elección. Las opciones posibles son: ME_OPCION_PASO y ME_OPCION_GEN
MODO_ELECCION = ME_OPCION_GEN

MC_STATUS_CHOICE = Choices(
    # Cargas parcial divergentes sin consolidar
    ('parcial_en_conflicto', 'parcial en conflicto'),
    # Carga parcial única (no CSV) o no coincidente.
    ('parcial_sin_consolidar', 'parcial sin consolidar'),
    # No hay cargas.
    ('sin_cargar', 'sin cargar'),
    # No hay dos cargas mínimas coincidentes, pero una es de CSV.
    ('parcial_consolidada_csv', 'parcial consolidada CSV'),
    # Carga parcial consolidada por multicarga.
    ('parcial_consolidada_dc', 'parcial consolidada doble carga'),
    ('total_sin_consolidar', 'total sin consolidar'),
    ('total_en_conflicto', 'total en conflicto'),
    ('total_consolidada_csv', 'total consolidada CSV'),
    ('total_consolidada_dc', 'total consolidada doble carga'),
    # No siguen en la carga.
    ('con_problemas', 'con problemas')
)

CONSTANCE_ADDITIONAL_FIELDS = {
    'status_text': [
        'elecciones.fields.StatusTextField', {
            'widget': 'django.forms.Textarea'
        },
    ],
    'rich_text': [
        'django.forms.fields.CharField', {
            'widget': 'django_summernote.widgets.SummernoteWidget'
        },
    ]
}

CONSTANCE_BACKEND = 'constance.backends.database.DatabaseBackend'
# Deshabilitamos el caché de Constance, porque si los datos están en la misma BD no tiene sentido
# cachearlos ahí mismo.
CONSTANCE_DATABASE_CACHE_BACKEND = 'dbcache'
CONSTANCE_DATABASE_CACHE_AUTOFILL_TIMEOUT = None

CONSTANCE_CONFIG = {
    'CARGAR_OPCIONES_NO_PRIO_CSV' : (True, 'Al procesar CSVs se cargan las opciones no prioritarias.', bool),
    'COEFICIENTE_IDENTIFICACION_VS_CARGA': (1.5, 'Cuando la cola de identifación sea N se prioriza esa tarea.', float),
    'PRIORIDAD_STATUS': ('\n'.join(s[0] for s in MC_STATUS_CHOICE), 'orden de los status', 'status_text'),
    'CONFIGURACION_COMPUTO_PUBLICA': ('inicial', 'Nombre de la configuración que se utiliza para publicar resultados.'),
    'SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL': (150000, 'Valor de scoring que debe superar un fiscal para que la aplicación lo considere troll.', int),
    'SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA': (1, 'Cuánto aumenta el scoring de troll por una identificacion distinta a la confirmada.', int),
    'SCORING_TROLL_PROBLEMA_MESA_CATEGORIA_CON_CARGA_CONFIRMADA': (1, 'Cuánto aumenta el scoring de troll por poner "problema" en una MesaCategoria para la que se confirmaron cargas.', int),
    'SCORING_TROLL_PROBLEMA_DESCARTADO': (1, 'Cuánto aumenta el scoring de troll al descartarse un "problema" que él reporto.', int),
    'SCORING_TROLL_DESCUENTO_ACCION_CORRECTA': (1, 'Cuánto disminuye el scoring de troll para cada acción aceptada de un fiscal.', int),
    'MULTIPLICADOR_CANT_ASIGNACIONES_REALIZADAS': (2, 'Este multiplicador se utiliza al computar "cant_asignaciones_realizadas_redondeadas" en el schedulling de attachments y mesa-categorías.', int),
    'PAUSA_SCHEDULER': (10, 'Frecuencia de ejecución del scheduler (en segundos).', int),
    'PAUSA_IMPORTAR_EMAILS': (300, 'Frecuencia de ejecución del importador de actas por email (en segundos).', int),
    'FACTOR_LARGO_COLA_POR_USUARIOS_ACTIVOS': (1.5, 'Factor de multiplicación para agregar tareas.', float),
    'ASIGNAR_MESA_EN_EL_MOMENTO_SI_NO_HAY_COLA': (True, 'Asignar tareas en el momento si la cola está vacía?', bool),
    'COTA_INFERIOR_COLA_TAREAS': (100, 'Cantidad mínima de tareas que se encolan.', int),
    'BONUS_AFINIDAD_GEOGRAFICA': (10, 'Cuánta prioridad ganan las tareas del distrito en que viene trabajando une fiscal.', int),
    'UMBRAL_EXCLUIR_TAREAS_FISCAL': (1, 'Si hay menos de este número de usuaries actives, no le presentamos a le fiscal tareas en las que haya estado involucrade.', int),
    'QUIERO_VALIDAR_INTRO': (None, "Texto de explicación arriba de la página de incripción como validador/a", "rich_text"),
    'URL_VIDEO_INSTRUCTIVO': ('https://www.youtube.com/embed/n1osvzuFx7I', "URL al video instructivo", str)
}

# Sin este setting los archivos grandes quedan con los permisos mal.
# https://github.com/divio/django-filer/issues/1031
FILE_UPLOAD_PERMISSIONS = 0o644

APP_VERSION_NUMBER = 'dev'
ver_file = '/tmp/version/version.txt'
if os.path.isfile(ver_file):
    with open(ver_file) as v_file:
        APP_VERSION_NUMBER = v_file.read()

# Para los tests no se importan los local settings.
if not TESTING:
    try:
        from .local_settings import *  # noqa
    except ImportError:
        pass

USAR_DJANGO_DEBUG_TOOLBAR = False

if DEBUG and USAR_DJANGO_DEBUG_TOOLBAR:
    # Recordar el pip install django-debug-toolbar
    INTERNAL_IPS = ['172.20.0.1']
    MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
    INSTALLED_APPS += ['debug_toolbar']


OCULTAR_CANTIDADES_DE_ELECTORES = False

DEFAULT_BACKGROUND_IMAGE = 'img/default_background.jpg'   # relativo a static