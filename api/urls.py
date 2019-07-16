# -*- coding: utf-8 -*-
from django.urls import include, path
from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from rest_framework import permissions

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from . import views


swagger_info =  openapi.Info(
   title="La API del escrutinio del Frente de Todos",
   default_version='v1',
   #description="Escrutinio social paralelo / Democracia con códigos",
   #license=openapi.License(name="GPLv3 License"),
)

schema_view = get_schema_view(
   swagger_info, public=True, permission_classes=(permissions.AllowAny,)
)

urlpatterns = [
   path('actas/', views.subir_acta, name='actas'),
   path('actas/<foto_digest>/', views.identificar_acta, name='identificar-acta'),
   path('actas/<foto_digest>/votos/', views.cargar_votos, name='cargar-votos'),
    
   path('categorias/', views.listar_categorias, name='categorias'),
   path('categorias/<int:id_categoria>/opciones/', views.listar_opciones, name='opciones'),

   url(r'^token/$', TokenObtainPairView.as_view(), name='token_obtain_pair'),
   url(r'^token/refresh/$', TokenRefreshView.as_view(), name='token_refresh'),

   url(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   url(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   url(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc')
]
