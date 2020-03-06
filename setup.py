# -*- coding: utf-8 -*-
import os
import re
import sys

from setuptools import find_packages, setup
"""
linux:
rm -rf "dist/*";rm -rf "build/*";python3 setup.py bdist_wheel;twine upload "dist/*;rm -rf "dist/*";rm -rf "build/*""
win32:
rm -rf dist;rm -rf build;python3 setup.py bdist_wheel;twine upload "dist/*";rm -rf dist;rm -rf build;rm -rf watchdogs.egg-info
"""

py_version = sys.version_info
if py_version.major < 3 or py_version.minor < 6:
    raise RuntimeError('Only support python3.6+')

with open('requirements.txt') as f:
    install_requires = [line for line in f.read().strip().split('\n')]

with open("README.md", encoding="u8") as f:
    long_description = f.read()

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'watchdogs', '__init__.py'), encoding="u8") as f:
    matched = re.search(r'''__version__ = ['"](.*?)['"]''', f.read())
    if not matched:
        raise ValueError('Not find the __version__ info.')
    version = matched.group(1)

description = "The whole thing is to keep some watchdogs to monitor the web's change. Read more: https://github.com/ClericPy/watchdogs."

setup(
    name="watchdogs",
    version=version,
    keywords="requests crawler uniparser torequests fastapi watchdog",
    description=description,
    long_description=long_description,
    long_description_content_type='text/markdown',
    license="MIT License",
    install_requires=install_requires,
    py_modules=["watchdogs"],
    package_data={'watchdogs': ['templates/*.html', 'static/*.ico']},
    extras_require={},
    classifiers=[
        "License :: OSI Approved :: MIT License",
        'Programming Language :: Python',
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    author="ClericPy",
    author_email="clericpy@gmail.com",
    url="https://github.com/ClericPy/watchdogs",
    packages=find_packages(),
    platforms="any",
)
