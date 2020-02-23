# -*- coding: utf-8 -*-
import os
import re
import sys

from setuptools import find_packages, setup
"""
linux:
rm -rf "dist/*";rm -rf "build/*";python3 setup.py bdist_wheel;twine upload "dist/*;rm -rf "dist/*";rm -rf "build/*""
win32:
rm -rf dist;rm -rf build;python3 setup.py bdist_wheel;twine upload "dist/*";rm -rf dist;rm -rf build;rm -rf uniparser.egg-info
"""

py_version = sys.version_info
if py_version.major < 3 or py_version.minor < 7:
    raise RuntimeError('Only support python3.7+')

with open('requirements.txt') as f:
    install_requires = [line for line in f.read().strip().split('\n')]

with open("README.md", encoding="u8") as f:
    long_description = f.read()

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'uniparser', '__init__.py'), encoding="u8") as f:
    version = re.search(r'''__version__ = ['"](.*?)['"]''', f.read()).group(1)

setup(
    name="uniparser",
    version=version,
    keywords=
    ("requests crawler parser tools universal lxml beautifulsoup bs4 jsonpath udf"
    ),
    description=
    "Provide a universal solution for crawler platforms. Read more: https://github.com/ClericPy/uniparser.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license="MIT License",
    install_requires=install_requires,
    py_modules=["uniparser"],
    package_data={'uniparser': ['templates/*.html']},
    extras_require={
        'requests': ['requests'],
        'httpx': ['httpx'],
        'aiohttp': ['aiohttp'],
        'torequests': ['torequests'],
        'all': ['torequests', 'httpx', 'requests', 'aiohttp'],
    },
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
    url="https://github.com/ClericPy/uniparser",
    packages=find_packages(),
    platforms="any",
)
