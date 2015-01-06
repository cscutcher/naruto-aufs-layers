# -*- coding: utf-8 -*-
"""
Setup for naruto aufs snapshot tool
"""
import sys
if sys.version_info < (3,):
    raise Exception('Naruto only supports python 3')


import logging
from setuptools import setup, find_packages

DEV_LOGGER = logging.getLogger(__name__)

test_requirements = ('nose>=1.0', 'coverage')


setup_kwargs = {
    'name': 'naruto_aufs_snapshot',
    'version': '0.1',
    'packages': find_packages(),
    'install_requires': ('sh', 'click', 'ipdb') + test_requirements,
    'setup_requires': test_requirements,
    'entry_points': {
        'console_scripts': [
            'naruto=naruto.cli:naruto_cli',
            'naruto-demo=naruto.demo:demo_cli',
        ]
    },
}

setup(**setup_kwargs)
