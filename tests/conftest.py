import contextlib
import json
import os
from functools import partial

import pkg_resources
import pytest
from pip._vendor.packaging.version import Version
from pip._vendor.pkg_resources import Requirement
from pytest import fixture

from prequ.cache import DependencyCache
from prequ.exceptions import NoCandidateFound
from prequ.repositories.base import BaseRepository
from prequ.resolver import Resolver
from prequ.utils import (
    as_tuple, key_from_ireq, key_from_req, make_install_requirement,
    name_from_req)

from .dirs import FAKE_PYPI_WHEELS_DIR

try:
    # pip<=9.x.x
    from pip.req import InstallRequirement
except ImportError:
    # pip>=10.0.0
    from pip._internal.req import InstallRequirement


class FakeRepository(BaseRepository):
    def __init__(self):
        with open('tests/test_data/fake-index.json', 'r') as f:
            self.index = json.load(f)

        with open('tests/test_data/fake-editables.json', 'r') as f:
            self.editables = json.load(f)

    def get_hashes(self, ireq):
        # Some fake hashes
        return {
            'test:123',
            'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        }

    def find_best_match(self, ireq, prereleases=False):
        if ireq.editable:
            return ireq

        versions = list(ireq.specifier.filter(self.index[key_from_ireq(ireq)],
                                              prereleases=prereleases))
        if not versions:
            raise NoCandidateFound(ireq, self.index[key_from_ireq(ireq)], ['https://fake.url.foo'])
        best_version = max(versions, key=Version)
        return make_install_requirement(
            name_from_req(ireq).lower(), best_version, ireq.extras,
            constraint=ireq.constraint)

    def _get_dependencies(self, ireq):
        if ireq.editable:
            return self.editables[str(ireq.link)]

        name, version, extras = as_tuple(ireq)
        # Store non-extra dependencies under the empty string
        extras += ("",)
        dependencies = [dep for extra in extras for dep in self.index[name][version][extra]]
        return [InstallRequirement.from_line(dep, constraint=ireq.constraint) for dep in dependencies]


class FakeInstalledDistribution(pkg_resources.Distribution):
    def __init__(self, line, deps=None):
        if deps is None:
            deps = []
        self.deps = [Requirement.parse(d) for d in deps]

        self.req = Requirement.parse(line)

        self._key = key_from_req(self.req)
        self.specifier = self.req.specifier

        self._version = line.split("==")[1]

    def requires(self):
        return self.deps

    def as_requirement(self):
        return self.req


@fixture
def fake_dist():
    return FakeInstalledDistribution


@fixture
def repository():
    return FakeRepository()


@fixture
def depcache(tmpdir):
    return DependencyCache(str(tmpdir))


@fixture
def resolver(depcache, repository):
    # TODO: It'd be nicer if Resolver instance could be set up and then
    #       use .resolve(...) on the specset, instead of passing it to
    #       the constructor like this (it's not reusable)
    return partial(Resolver, repository=repository, cache=depcache)


@fixture
def base_resolver(depcache):
    return partial(Resolver, cache=depcache)


@fixture
def from_line():
    return InstallRequirement.from_line


@fixture
def from_editable():
    return InstallRequirement.from_editable


@fixture
def fake_package_dir():
    return os.path.join(os.path.split(__file__)[0], 'test_data', 'fake_package')


@fixture
def small_fake_package_dir():
    return os.path.join(os.path.split(__file__)[0], 'test_data', 'small_fake_package')


@fixture
def minimal_wheels_dir():
    return os.path.join(os.path.split(__file__)[0], 'test_data', 'minimal_wheels')


@pytest.yield_fixture
def pip_conf(tmpdir):
    with get_temporary_pip_conf(tmpdir) as path:
        yield path


@pytest.yield_fixture
def pip_conf_with_index(tmpdir):
    with get_temporary_pip_conf(tmpdir, index='http://localhost') as path:
        yield path


@pytest.yield_fixture
def pip_conf_with_wheeldir(tmpdir):
    with get_temporary_pip_conf(tmpdir, wheeldir=True) as path:
        yield path


@contextlib.contextmanager
def get_temporary_pip_conf(tmpdir, index=None, wheeldir=False):
    pip_conf_file = 'pip.conf' if os.name != 'nt' else 'pip.ini'
    path = (tmpdir / pip_conf_file).strpath
    index_line = ('index-url = ' + index) if index else 'no-index = yes'
    wheeldir_line = (
        'find-links = {}\n'.format(FAKE_PYPI_WHEELS_DIR) if wheeldir else '')
    with open(path, 'w') as f:
        f.write(
            '[global]\n'
            + index_line + '\n'
            + wheeldir_line +
            'trusted-host = localhost\n')
    old_value = os.environ.get('PIP_CONFIG_FILE')
    try:
        os.environ['PIP_CONFIG_FILE'] = path
        yield path
    finally:
        if old_value is not None:
            os.environ['PIP_CONFIG_FILE'] = old_value
        else:
            del os.environ['PIP_CONFIG_FILE']
        os.remove(path)
