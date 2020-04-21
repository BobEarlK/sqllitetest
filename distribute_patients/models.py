from django.db import models


# Create your models here.
class Testmodel(models.Model):
    testy = models.CharField(max_length=7)
