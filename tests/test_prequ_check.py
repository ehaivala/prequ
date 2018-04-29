from __future__ import unicode_literals

import pytest

from prequ.scripts.check import main as check_main

from .dirs import FAKE_PYPI_WHEELS_DIR
from .utils import check_successful_exit, make_cli_runner

try:
    # pip<=9.x.x
    from pip.exceptions import DistributionNotFound
except ImportError:
    # pip>=10.0.0
    from pip._internal.exceptions import DistributionNotFound

run_check = make_cli_runner(check_main, [])


UP_TO_DATE_REQ_TXT = """
--trusted-host localhost

tiny-dependee==1.0
tiny-depender==1.1
""".lstrip()

OUTDATED_REQ_TXT = UP_TO_DATE_REQ_TXT.replace('==1.1', '')

TXT_CONTENTS = {
    'up_to_date': UP_TO_DATE_REQ_TXT,
    'outdated': OUTDATED_REQ_TXT,
}


@pytest.mark.parametrize('txt_status', ['up_to_date', 'outdated'])
@pytest.mark.parametrize('mode', ['default', 'silent', 'verbose'])
def test_simple_case(pip_conf, txt_status, mode):
    out = run_check(pip_conf, TXT_CONTENTS[txt_status], mode)
    if txt_status == 'up_to_date':
        check_successful_exit(out)
        if mode in ('default', 'verbose'):
            expected_output = 'requirements.txt is OK\n'
        elif mode == 'silent':
            expected_output = ''
    else:
        assert out.exit_code == 1
        if mode == 'default':
            expected_output = 'requirements.txt is outdated\n'
        elif mode == 'verbose':
            expected_output = (
                '--- requirements.txt (current)\n'
                '+++ requirements.txt (expected)\n'
                '@@ -1,4 +1,4 @@\n'
                ' --trusted-host localhost\n'
                ' \n'
                ' tiny-dependee==1.0\n'
                '-tiny-depender\n'
                '+tiny-depender==1.1\n'
                'requirements.txt is outdated\n')
        elif mode == 'silent':
            expected_output = ''
    assert out.output == expected_output


@pytest.mark.parametrize('mode', ['default', 'silent', 'verbose'])
def test_error_in_input(pip_conf, mode):
    with pytest.raises(DistributionNotFound) as excinfo:
        run_check(pip_conf, 'tiny-dependee==0.1\n', mode)
    assert '{}'.format(excinfo.value) == (
        'No matching distribution found for tiny-dependee==0.1')


def run_check(pip_conf, txt_content, mode='default'):
    check_args = {'default': [], 'silent': ['-s'], 'verbose': ['-v']}[mode]
    runner = make_cli_runner(check_main, check_args)
    conf = {
        'options': {'wheel_dir': FAKE_PYPI_WHEELS_DIR},
        'requirements': ['tiny-depender'],
        'existing_out_files': {'requirements.txt': txt_content},
    }
    with runner(pip_conf, **conf) as out:
        return out
