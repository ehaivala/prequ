import os

from prequ.exceptions import (
    IncompatibleRequirements, NoCandidateFound, UnsupportedConstraint)

from .dirs import FAKE_PYPI_WHEELS_DIR

try:
    # pip<=9.x.x
    from pip.index import InstallationCandidate
    from pip.req import InstallRequirement
except ImportError:
    # pip>=10.0.0
    from pip._internal.index import InstallationCandidate
    from pip._internal.req import InstallRequirement


def test_no_candidate_found_with_versions():
    ireq = InstallRequirement.from_line('some-package==12.3.4')
    tried = [
        InstallationCandidate('some-package', ver, None)
        for ver in ['1.2.3', '12.3.0', '12.3.5']]
    no_candidate_found = NoCandidateFound(ireq, tried, ['pypi.localhost'])
    assert '{}'.format(no_candidate_found) == (
        "Could not find a version that matches some-package==12.3.4\n"
        "Tried: 1.2.3, 12.3.0, 12.3.5\n"
        "There are incompatible versions in the resolved dependencies.")


def test_no_candidate_found_no_versions():
    ireq = InstallRequirement.from_line('some-package==12.3.4')
    tried = []
    no_candidate_found = NoCandidateFound(ireq, tried, ['pypi.localhost'])
    assert '{}'.format(no_candidate_found) == (
        "Could not find a version that matches some-package==12.3.4\n"
        "Tried: (no version found at all)\n"
        "Was pypi.localhost reachable?")


def test_unsupported_constraint_simple():
    msg = "Foo bar distribution is not supported"
    ireq = InstallRequirement.from_line('foo-bar')
    unsupported_constraint = UnsupportedConstraint(msg, ireq)
    assert '{}'.format(unsupported_constraint) == (
        "Foo bar distribution is not supported (constraint was: foo-bar)")


def test_unsupported_constraint_editable_wheel():
    wheel_path = os.path.join(
        FAKE_PYPI_WHEELS_DIR, 'small_fake_a-0.1-py2.py3-none-any.whl')
    msg = "Editable wheel is too square"
    ireq_wheel = InstallRequirement.from_line(wheel_path)
    ireq = InstallRequirement.from_editable(str(ireq_wheel.link))
    unsupported_constraint = UnsupportedConstraint(msg, ireq)
    assert '{}'.format(unsupported_constraint) == (
        "Editable wheel is too square (constraint was: {})".format(ireq))


def test_incompatible_requirements():
    ireq_a = InstallRequirement.from_line('dummy==1.5')
    ireq_b = InstallRequirement.from_line('dummy==2.6')
    incompatible_reqs = IncompatibleRequirements(ireq_a, ireq_b)
    assert '{}'.format(incompatible_reqs) == (
        "Incompatible requirements found: dummy==1.5 and dummy==2.6")
