# -*- coding: utf-8 -*-
from django.urls import include, path
from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from rest_framework import permissions

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from . import views

schema_view = get_schema_view(
   openapi.Info(
      title="La API del escrutinio social paralelo",
      default_version='v1',
      description="Escrutinio social paralelo / Democracia con codigos",
      license=openapi.License(name="GPLv3 License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    url(r'^actas/$', views.subir_acta, name='actas'),
    path('actas/<foto_digest>/', views.identificar_acta, name='identificar-acta'),
    path('actas/<foto_digest>/votos/', views.cargar_votos, name='cargar-votos'),

    url(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc')
]
