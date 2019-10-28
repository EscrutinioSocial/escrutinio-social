from django.db import models

class BackgroundImage(models.Model):
    img = models.ImageField(upload_to='backgrounds')

