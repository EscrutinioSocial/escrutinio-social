import pytest
from random import shuffle
from django.core.exceptions import ValidationError
from elecciones.fields import StatusTextField


@pytest.mark.parametrize('input', [
    '',
    'foo',
])
def test_statustextfield_empty(db, input):
    s = StatusTextField()
    with pytest.raises(ValidationError):
        s.clean(input)


def test_statustextfield_valid(db,):
    from constance import config

    s = StatusTextField()

    default = config.PRIORIDAD_STATUS
    new = default.split()
    shuffle(new)
    new = '\n'.join(new)
    s.clean(new)
