# custom_storages.py
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    location = settings.STATICFILES_AWS_LOCATION


class MediaStorage(S3Boto3Storage):
    location = settings.MEDIAFILES_AWS_LOCATION
