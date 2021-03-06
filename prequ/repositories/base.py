# coding: utf-8
from __future__ import (
    absolute_import, division, print_function, unicode_literals)

from abc import ABCMeta, abstractmethod

from six import add_metaclass

from ..utils import is_pinned_requirement


@add_metaclass(ABCMeta)
class BaseRepository(object):

    def clear_caches(self):
        """Should clear any caches used by the implementation."""

    def freshen_build_caches(self):
        """Should start with fresh build/source caches."""

    @abstractmethod
    def find_best_match(self, ireq):
        """
        Return a Version object that indicates the best match for the given
        InstallRequirement according to the repository.
        """

    def get_dependencies(self, ireq):
        """
        Given a pinned or an editable InstallRequirement, returns a set of
        dependencies (also InstallRequirements, but not necessarily pinned).
        They indicate the secondary dependencies for the given requirement.
        """
        if not (ireq.editable or is_pinned_requirement(ireq)):
            raise TypeError('Expected pinned or editable InstallRequirement, got {}'.format(ireq))
        return self._get_dependencies(ireq)

    def prepare_ireq(self, ireq):
        """
        Prepare install requirement for requirement analysis.

        Downloads and unpacks the sources to get the egg_info etc.
        Note: For URLs or local paths even key_from_ireq(ireq) might
        fail before this is done.

        :type ireq: pip.req.InstallRequirement
        """
        self._get_dependencies(ireq)

    @abstractmethod
    def _get_dependencies(self, ireq):
        pass

    @abstractmethod
    def get_hashes(self, ireq):
        """
        Given a pinned InstallRequire, returns a set of hashes that represent
        all of the files for a given requirement. It is not acceptable for an
        editable or unpinned requirement to be passed to this function.
        """
