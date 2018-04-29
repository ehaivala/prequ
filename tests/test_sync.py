import os
import sys
from collections import Counter

import mock
import pytest

from prequ.exceptions import IncompatibleRequirements
from prequ.sync import dependency_tree, diff, merge, sync
from prequ.utils import get_ireq_version, key_from_dist, normalize_req_name

try:
    # pip<=9.x.x
    from pip.download import path_to_url, url_to_path
except ImportError:
    # pip>=10.0.0
    from pip._internal.download import path_to_url, url_to_path


@pytest.mark.parametrize(
    ('installed', 'root', 'expected'),

    [
        ([],
            'prequ', []),

        ([('prequ==1', [])],
            'prequ', ['prequ']),

        ([('prequ==1', []),
          ('django==1.7', [])],
            'prequ', ['prequ']),

        ([('prequ==1', ['click>=2']),
          ('django==1.7', []),
          ('click==3', [])],
            'prequ', ['prequ', 'click']),

        ([('prequ==1', ['click>=2']),
          ('django==1.7', []),
          ('click==1', [])],
            'prequ', ['prequ']),

        ([('root==1', ['child==2']),
          ('child==2', ['grandchild==3']),
          ('grandchild==3', [])],
            'root', ['root', 'child', 'grandchild']),

        ([('root==1', ['child==2']),
          ('child==2', ['root==1'])],
            'root', ['root', 'child']),
    ]
)
def test_dependency_tree(fake_dist, installed, root, expected):
    installed = {key_from_dist(distribution): distribution
                 for distribution in
                 (fake_dist(name, deps) for name, deps in installed)}

    root_key = normalize_req_name(root)
    actual = dependency_tree(installed, root_key)
    assert actual == set(expected)


def test_merge_detect_conflicts(from_line):
    requirements = [from_line('flask==1'), from_line('flask==2')]

    with pytest.raises(IncompatibleRequirements):
        merge(requirements, ignore_conflicts=False)


def test_merge_ignore_conflicts(from_line):
    requirements = [from_line('flask==1'), from_line('flask==2')]

    assert Counter(requirements[1:2]) == Counter(merge(requirements, ignore_conflicts=True))


def test_merge(from_line):
    requirements = [from_line('flask==1'),
                    from_line('flask==1'),
                    from_line('django==2')]

    assert Counter(requirements[1:3]) == Counter(merge(requirements, ignore_conflicts=True))


def test_diff_should_do_nothing():
    installed = []  # empty env
    reqs = []  # no requirements

    to_install, to_uninstall = diff(reqs, installed)
    assert to_install == set()
    assert to_uninstall == set()


def test_diff_should_install(from_line):
    installed = []  # empty env
    reqs = [from_line('django==1.8')]

    to_install, to_uninstall = diff(reqs, installed)
    assert {str(x.req) for x in to_install} == {'django==1.8'}
    assert to_uninstall == set()


def test_diff_should_uninstall(fake_dist):
    installed = [fake_dist('django==1.8')]
    reqs = []

    to_install, to_uninstall = diff(reqs, installed)
    assert to_install == set()
    assert to_uninstall == {'django'}  # no version spec when uninstalling


def test_diff_should_not_uninstall(fake_dist):
    ignored = ('pip==7.1.0', 'prequ==1.0.0', 'pip-review==1.1.1',
               'pkg-resources==0.0.0', 'setuptools==34.0.0', 'wheel==0.29.0')
    installed = [fake_dist(pkg) for pkg in ignored]
    reqs = []

    to_uninstall = diff(reqs, installed)[1]
    assert to_uninstall == set()


def test_diff_should_update(fake_dist, from_line):
    installed = [fake_dist('django==1.7')]
    reqs = [from_line('django==1.8')]

    to_install, to_uninstall = diff(reqs, installed)
    assert {str(x.req) for x in to_install} == {'django==1.8'}
    assert to_uninstall == set()


def test_diff_should_install_with_markers(from_line):
    installed = []
    reqs = [from_line("subprocess32==3.2.7 ; python_version=='2.7'")]

    to_install, to_uninstall = diff(reqs, installed)
    assert {str(x.req) for x in to_install} == ({'subprocess32==3.2.7'} if sys.version.startswith('2.7') else set())
    assert to_uninstall == set()


def test_diff_should_uninstall_with_markers(fake_dist, from_line):
    installed = [fake_dist('subprocess32==3.2.7')]
    reqs = [from_line("subprocess32==3.2.7 ; python_version=='2.7'")]

    to_install, to_uninstall = diff(reqs, installed)
    assert to_install == set()
    assert to_uninstall == (set() if sys.version.startswith('2.7') else {'subprocess32'})


def test_diff_leave_packaging_packages_alone(fake_dist, from_line):
    # Suppose an env contains Django, and pip itself
    installed = [
        fake_dist('django==1.7'),
        fake_dist('first==2.0.1'),
        fake_dist('pip==7.1.0'),
    ]

    # Then this Django-only requirement should keep pip around (i.e. NOT
    # uninstall it), but uninstall first
    reqs = [
        from_line('django==1.7'),
    ]

    to_install, to_uninstall = diff(reqs, installed)
    assert to_install == set()
    assert to_uninstall == {'first'}


def test_diff_leave_prequ_alone(fake_dist, from_line):
    # Suppose an env contains Django, and prequ itself (including all of
    # its dependencies)
    installed = [
        fake_dist('django==1.7'),
        fake_dist('first==2.0.1'),
        fake_dist('prequ==1.1.1', [
            'click>=4',
            'first',
            'six',
        ]),
        fake_dist('six==1.9.0'),
        fake_dist('click==4.1'),
        fake_dist('foobar==0.3.6'),
    ]

    # Then this Django-only requirement should keep pip around (i.e. NOT
    # uninstall it), but uninstall first
    reqs = [
        from_line('django==1.7'),
    ]

    to_install, to_uninstall = diff(reqs, installed)
    assert to_install == set()
    assert to_uninstall == {'foobar'}


def test_diff_with_editable(
        fake_dist, from_editable, from_line, small_fake_package_dir):
    installed = [
        fake_dist('small-fake-with-deps==0.0.1'),
        fake_dist('six==1.10.0'),
    ]
    reqs = [
        from_editable(small_fake_package_dir),
        from_line('six==1.10.0'),
    ]
    to_install, to_uninstall = diff(reqs, installed)

    assert to_uninstall == set(), "No packages should be uninstalled"

    # The editable should be upgraded, since the installed version
    # (0.0.1) was different than the version specified in setup.py of
    # the editable package (0.1)
    assert len(to_install) == 1
    package = list(to_install)[0]
    assert package.editable
    assert str(package.link) == path_to_url(small_fake_package_dir)


def test_diff_with_editable_without_changes(
        fake_dist, from_editable, from_line, small_fake_package_dir):
    installed = [
        fake_dist('small-fake-with-deps==0.1'),
        fake_dist('six==1.10.0'),
    ]
    reqs = [
        from_editable(small_fake_package_dir),
        from_line('six==1.10.0'),
    ]
    assert reqs[0].req is None, "Editable doesn't have Requirement data yet"

    to_install, to_uninstall = diff(reqs, installed)

    assert reqs[0].req is not None, "Requirement data has been filled"
    pinned_ver = get_ireq_version(reqs[0])
    assert installed[0].version == pinned_ver

    assert to_uninstall == set(), "No packages should be uninstalled"
    assert to_install == set(), "No packages should be (re)installed"


@pytest.mark.parametrize(
    'lines',
    [
        ['django==1.8'],
        ['django==1.8', 'click==4.0'],
    ]
)
def test_sync_install(from_line, lines):
    with mock.patch('prequ.sync.check_call') as check_call:
        to_install = {from_line(line) for line in lines}

        sync(to_install, set())
        check_call.assert_called_once_with(['pip', 'install', '-q'] + sorted(lines))


def test_sync_with_editable(from_editable, small_fake_package_dir):
    with mock.patch('prequ.sync.check_call') as check_call:
        to_install = {from_editable(small_fake_package_dir)}

        sync(to_install, set())
        check_call.assert_called_once_with(
            ['pip', 'install', '-q',
             '-e', path_to_url(small_fake_package_dir)])


def test_sync_with_editable_uses_abspath(from_editable, small_fake_package_dir):
    ireq = from_editable(small_fake_package_dir)
    rel_path = os.path.relpath(url_to_path(ireq.link.url))
    ireq.link.url = 'file:{}'.format(rel_path.replace(os.path.sep, '/'))
    with mock.patch('prequ.sync.check_call') as check_call:
        sync({ireq}, set())
        check_call.assert_called_once_with(
            ['pip', 'install', '-q',
             '-e', path_to_url(os.path.abspath(small_fake_package_dir))])


def test_sync_sorting_ireqs(from_line):
    with mock.patch('prequ.sync.check_call') as check_call:
        to_install = {from_line('django==1.8'), from_line('first==2.0.1')}
        sync(to_install, {})
        check_call.assert_called_once_with(
            ['pip', 'install', '-q', 'django==1.8', 'first==2.0.1'])


def test_sync_sorting_ireqs_with_editable(from_line, from_editable):
    with mock.patch('prequ.sync.check_call') as check_call:
        path_to_package = os.path.join(os.path.dirname(__file__),
                                       'test_data', 'small_fake_package')
        editable_ireq = from_editable(path_to_package)
        to_install = {
            from_line('django==1.8'),
            from_line('first==2.0.1'),
            editable_ireq,
        }
        sync(to_install, {})
        check_call.assert_called_once_with(
            ['pip', 'install', '-q',
             'django==1.8', 'first==2.0.1', '-e', str(editable_ireq.link)])
