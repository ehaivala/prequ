import re

import mock
import pytest

from prequ.repositories.local import LocalRequirementsRepository
from prequ.repositories.pypi import PyPIRepository
from prequ.utils import key_from_ireq

try:
    # pip<=9.x.x
    from pip.req import InstallRequirement
except ImportError:
    # pip>=10.0.0
    from pip._internal.req import InstallRequirement


def ireq(line, extras=None):
    sorted_extras = ','.join(sorted((extras or '').split(',')))
    extras_str = '[{}]'.format(sorted_extras) if sorted_extras else ''
    parts = re.split('([<>=])', line)
    line_with_extras = parts[0] + extras_str + ''.join(parts[1:])
    return InstallRequirement.from_line(line_with_extras)


@pytest.mark.parametrize('existing_pin,to_find,pin_matches', [
    ('foobar==1.2.4', 'foobar>=1.2.3', True),
    ('foobar==1.2.2', 'foobar>=1.2.3', False),
    ('foobar==1.2.4', 'foobar', True),
    ('foobar==1.2.4', 'baz', False),
    (None, 'foobar', False),
])
@pytest.mark.parametrize('pinned_extras,requested_extras', [
    (None, None),
    ('pinned_extra', None),
    (None, 'new_extra'),
    ('p1,p2', 'p2,n3'),
])
def test_find_best_match(existing_pin, to_find, pin_matches,
                         pinned_extras, requested_extras):
    fallback_repo = mock.create_autospec(PyPIRepository)
    fallback_repo.find_best_match.return_value = 'fallback_result'
    pin = ireq(existing_pin, pinned_extras) if existing_pin else None
    existing_pins = {key_from_ireq(pin): pin} if pin else {}
    repo = LocalRequirementsRepository(existing_pins, fallback_repo)
    ireq_to_find = ireq(to_find, requested_extras)
    result = repo.find_best_match(ireq_to_find)
    if pin_matches:
        assert repr(result) == repr(ireq(existing_pin, requested_extras))
    else:
        fallback_repo.find_best_match.assert_called_with(ireq_to_find, None)
        assert result == 'fallback_result'


def test_find_best_match_preserves_period():
    fallback_repo = mock.create_autospec(PyPIRepository)
    pin = ireq('foo.bar==42.0')
    existing_pins = {key_from_ireq(pin): pin}
    repo = LocalRequirementsRepository(existing_pins, fallback_repo)
    result = repo.find_best_match(ireq('foo.bar'))
    assert repr(result) == repr(ireq('foo.bar==42.0'))
