from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^(?P<attachment_id>\d+)/$', views.ProblemaResolve.as_view(), name='confirmar-problema'),
    url(r'^(?P<attachment_id>\d+)/$', views.ProblemaResolve.as_view(), name='descartar-problema'),
]
