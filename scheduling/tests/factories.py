import factory
from factory.django import DjangoModelFactory


class PrioridadSchedulingFactory(DjangoModelFactory):

    class Meta:
        model = 'scheduling.PrioridadScheduling'
