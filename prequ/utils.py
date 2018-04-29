# coding: utf-8
from __future__ import (
    absolute_import, division, print_function, unicode_literals)

import os
import re
import sys
from collections import OrderedDict
from itertools import chain, groupby

from click import style

try:
    # pip<=9.x.x
    import pip
    from pip.download import path_to_url, url_to_path
    from pip.req import InstallRequirement
except ImportError:
    # pip>=10.0.0
    from pip import _internal as pip
    from pip._internal.download import path_to_url, url_to_path
    from pip._internal.req import InstallRequirement


def first(iterable):
    for x in iterable:
        return x
    return None


def safeint(s):
    try:
        return int(s)
    except ValueError:
        return 0


pip_version_info = tuple(safeint(digit) for digit in pip.__version__.split('.'))

UNSAFE_PACKAGES = {'setuptools', 'distribute', 'pip'}


def assert_compatible_pip_version():
    # Make sure we're using a reasonably modern version of pip
    if not pip_version_info >= (8, 0):
        raise SystemExit((
            'Prequ requires at least version 8.0 of pip ({} found), '
            'perhaps run `pip install --upgrade pip`?').format(pip.__version__))


def key_from_ireq(ireq):
    """
    Get a normalized key for an InstallRequirement.

    :type ireq: InstallRequirement|.resolver.RequirementSummary
    :rtype: str
    """
    # from .resolver import RequirementSummary
    # assert isinstance(ireq, InstallRequirement) or (
    #     isinstance(ireq, RequirementSummary)), repr(ireq)
    return normalize_req_name(name_from_ireq(ireq))


def name_from_ireq(ireq):
    """
    Get the distribution name from an InstallRequirement.

    :type ireq: InstallRequirement|.resolver.RequirementSummary
    :rtype: str
    """
    if not ireq.req:
        ireq.source_dir = os.path.abspath(ireq.source_dir)
        ireq.run_egg_info()
        assert ireq.req, "run_egg_info should fill req: {!r}".format(ireq)
    return name_from_req(ireq.req)


def key_from_req(req):
    """
    Get normalized key of a requirement.

    :type req: packaging.requirements.Requirement
    :rtype: str
    """
    return normalize_req_name(name_from_req(req))


def name_from_req(req):
    """
    Get the distribution name from a requirement.

    :type req: packaging.requirements.Requirement
    :rtype: str
    """
    # import packaging.requirements
    # import pkg_resources
    # assert isinstance(req, packaging.requirements.Requirement) or (
    #     isinstance(req, pip._vendor.packaging.requirements.Requirement) or
    #     isinstance(req, pkg_resources.Requirement)), (type(req), repr(req))
    #
    # Note: On pip 8.1.1 req doesn't have a name but has a key
    return req.name if hasattr(req, 'name') else req.key


def key_from_dist(dist):
    """
    Get normalized key of a distribution.

    :type dist: pkg_resources.Distribution
    :rtype: str
    """
    # import pkg_resources
    # assert isinstance(dist, pkg_resources.Distribution) or (
    #     isinstance(dist, pip._vendor.pkg_resources.Distribution)), repr(dist)
    return normalize_req_name(dist.key)


def normalize_req_name(name):
    """
    Normalize name of a requirement (in the style of PEP 503).

    >>> str(normalize_req_name('hello'))
    'hello'

    >>> str(normalize_req_name('hello_world'))
    'hello-world'

    >>> str(normalize_req_name('foo.bar--ding__dong'))
    'foo-bar-ding-dong'

    :type name: str
    :rtype: str
    """
    return _REQUIREMENT_NORMALIZE_RX.sub('-', name).lower()


_REQUIREMENT_NORMALIZE_RX = re.compile(r'[-_.]+')


def check_is_hashable(ireq):
    if ireq.editable:
        raise ValueError("Cannot hash editable requirement: {}".format(ireq))
    if is_vcs_link(ireq):
        raise ValueError("Cannot hash VCS link requirement: {}".format(ireq))
    if not is_pinned_requirement(ireq):
        raise ValueError("Cannot hash unpinned requirement: {}".format(ireq))


def comment(text):
    return style(text, fg='green')


def make_install_requirement(name, version, extras, constraint=False):
    # If no extras are specified, the extras string is blank
    extras_string = ""
    if extras:
        # Sort extras for stability
        extras_string = "[{}]".format(",".join(sorted(extras)))

    return InstallRequirement.from_line(
        str('{}{}=={}'.format(name, extras_string, version)),
        constraint=constraint)


def is_subdirectory(base, directory):
    """
    Return True if directory is a child directory of base
    """
    abs_base = os.path.abspath(fs_str(base))
    abs_dir = os.path.abspath(fs_str(directory))
    (base_drive, base_path) = os.path.splitdrive(abs_base)
    (dir_drive, dir_path) = os.path.splitdrive(abs_dir)
    if base_drive.lower() != dir_drive.lower():
        return False
    relpath = os.path.relpath(abs_dir, start=abs_base)
    return relpath.split(os.path.sep, 1)[0] != os.path.pardir


def format_requirement(ireq, marker='', root_dir=None, find_links_dirs=None):
    """
    Generic formatter for pretty printing InstallRequirements to the terminal
    in a less verbose way than using its `__str__` method.

    :type ireq: InstallRequirement
    :type marker: str
    :type root_dir: str|None
    :type find_links_dirs: list[str]|None
    """
    line_format = formatted_as(ireq, find_links_dirs)
    if line_format in ['path', 'url']:
        url_or_path = _format_link(ireq.link, root_dir)
        if ireq.editable:
            line = '-e {}'.format(url_or_path)
        elif ireq.link.scheme == 'file':
            line = '{}'.format(url_or_path)
        else:
            line = '{}#egg={}'.format(url_or_path, ireq.req)
    else:
        line = str(ireq.req).lower()

    if marker:
        line = '{} ; {}'.format(line, marker)

    return line


def formatted_as(ireq, find_links_dirs=None):
    from_findlink_dir = _find_local_source(ireq, find_links_dirs or [])
    if ireq.link and not ireq.link.comes_from and not from_findlink_dir:
        if ireq.link.scheme == 'file':
            return 'path'
        else:
            return 'url'
    return 'simple'


def _format_link(link, root_dir):
    """
    Format link as URL or path.

    :type link: pip.index.Link
    :type root_dir: str|None
    :rtype: str
    """
    if link.scheme != 'file':
        return link.url

    path = url_to_path(link.url)

    if root_dir is not None and is_subdirectory(root_dir, path):
        relpath = os.path.relpath(path, start=root_dir)
        if relpath == '.':
            return '.'
        return './' + relpath.replace(os.path.sep, '/')

    # Make sure it's absolute
    return path_to_url(path)


def _find_local_source(ireq, local_dirs):
    """
    Find if requirement comes from local directory and return it.
    """
    if not ireq.link or ireq.link.scheme != 'file':
        return None
    for local_dir in local_dirs:
        if is_subdirectory(local_dir, ireq.link.path):
            return local_dir
    return None


def format_specifier(ireq):
    """
    Generic formatter for pretty printing the specifier part of
    InstallRequirements to the terminal.
    """
    # TODO: Ideally, this is carried over to the pip library itself
    specs = ireq.specifier._specs if ireq.req is not None else []
    specs = sorted(specs, key=lambda x: x._spec[1])
    return ','.join(str(s) for s in specs) or '<any>'


def is_pinned_requirement(ireq):
    """
    Returns whether an InstallRequirement is a "pinned" requirement.

    An InstallRequirement is considered pinned if:

    - Is not editable
    - It has at least one "==" specifier with a version that is not a
      wildcard
    - It is not conflicting (i.e. filtering out all possible versions)

    Examples:

    >>> assert is_pinned_requirement('django==1.8')
    >>> assert not is_pinned_requirement('django>1.8')
    >>> assert not is_pinned_requirement('django~=1.8')
    >>> assert not is_pinned_requirement('django==1.8.*')
    >>> assert is_pinned_requirement('django>=1.4,==1.8')
    >>> assert not is_pinned_requirement('django>=1.4,<=1.4')
    >>> assert not is_pinned_requirement('django==1.8,==1.9')
    >>> assert not is_pinned_requirement('django==1.8,>=1.9')
    """
    return get_pinned_version(ireq) is not None


def get_pinned_version(ireq):
    """
    Get pinned version of a requirement, if it is pinned.

    :type ireq: InstallRequirement|str
    :type ignore_editables: bool
    """
    if not isinstance(ireq, InstallRequirement):
        ireq = InstallRequirement(ireq, None)
    assert isinstance(ireq, InstallRequirement)

    if ireq.editable:
        return None

    return get_ireq_version(ireq)


def get_ireq_version(ireq):
    """
    Get version of a requirement even if it's editable.

    :type ireq: InstallRequirement|str
    """
    if not ireq.req or not ireq.specifier or not ireq.specifier._specs:
        return None

    specs = (x._spec for x in ireq.specifier._specs)
    versions = set(
        version for (op, version) in specs
        if (op == '==' or op == '===') and not version.endswith('.*'))
    good_versions = ireq.specifier.filter(versions, prereleases=True)
    return first(good_versions)


def is_vcs_link(ireq):
    """
    Returns whether an InstallRequirement is a version control link.
    """

    return ireq.link is not None and not ireq.link.is_artifact


def as_tuple(ireq):
    """
    Pulls out the (name: str, version:str, extras:(str)) tuple from the pinned InstallRequirement.

    :type ireq: InstallRequirement
    """
    name = key_from_ireq(ireq)  # Runs also egg_info if needed
    version = get_ireq_version(ireq)
    extras = tuple(sorted(ireq.extras))
    return name, version, extras


def full_groupby(iterable, key=None):
    """Like groupby(), but sorts the input on the group key first."""
    return groupby(sorted(iterable, key=key), key=key)


def flat_map(fn, collection):
    """Map a function over a collection and flatten the result by one-level"""
    return chain.from_iterable(map(fn, collection))


def lookup_table(values, key=None, keyval=None, unique=False, use_lists=False):
    """
    Builds a dict-based lookup table (index) elegantly.

    Supports building normal and unique lookup tables.  For example:

    >>> assert lookup_table(
    ...     ['foo', 'bar', 'baz', 'qux', 'quux'], lambda s: s[0]) == {
    ...     'b': {'bar', 'baz'},
    ...     'f': {'foo'},
    ...     'q': {'quux', 'qux'}
    ... }

    For key functions that uniquely identify values, set unique=True:

    >>> assert lookup_table(
    ...     ['foo', 'bar', 'baz', 'qux', 'quux'], lambda s: s[0],
    ...     unique=True) == {
    ...     'b': 'baz',
    ...     'f': 'foo',
    ...     'q': 'quux'
    ... }

    The values of the resulting lookup table will be values, not sets.

    For extra power, you can even change the values while building up the LUT.
    To do so, use the `keyval` function instead of the `key` arg:

    >>> assert lookup_table(
    ...     ['foo', 'bar', 'baz', 'qux', 'quux'],
    ...     keyval=lambda s: (s[0], s[1:])) == {
    ...     'b': {'ar', 'az'},
    ...     'f': {'oo'},
    ...     'q': {'uux', 'ux'}
    ... }

    """
    if keyval is None:
        if key is None:
            keyval = (lambda v: v)
        else:
            keyval = (lambda v: (key(v), v))

    if unique:
        return dict(keyval(v) for v in values)

    lut = {}
    for value in values:
        k, v = keyval(value)
        try:
            s = lut[k]
        except KeyError:
            if use_lists:
                s = lut[k] = list()
            else:
                s = lut[k] = set()
        if use_lists:
            s.append(v)
        else:
            s.add(v)
    return dict(lut)


def dedup(iterable):
    """Deduplicate an iterable object like iter(set(iterable)) but
    order-reserved.
    """
    return iter(OrderedDict.fromkeys(iterable))


def fs_str(string):
    """
    Convert given string to a correctly encoded filesystem string.

    On Python 2, if the input string is unicode, converts it to bytes
    encoded with the filesystem encoding.

    On Python 3 returns the string as is, since Python 3 uses unicode
    paths and the input string shouldn't be bytes.

    >>> fs_str(u'some path component/Something')
    'some path component/Something'
    >>> assert isinstance(fs_str('whatever'), str)
    >>> assert isinstance(fs_str(u'whatever'), str)

    :type string: str|unicode
    :rtype: str
    """
    if isinstance(string, str):
        return string
    assert not isinstance(string, bytes)
    return string.encode(_fs_encoding)


_fs_encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
