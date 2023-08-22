#!/usr/bin/env python
from setuptools import setup

with open("README.rst") as f:
    readme = f.read()

setup(
    name="georgian-django-payments",
    author="graey",
    version='1.1',
    author_email="info@graey.ge",
    description="Georgian Payments",
    setup_requires=["setuptools_scm"],
    url="https://github.com/graey-ge/georgian-django-payments",
    packages=['payments'],
    classifiers=[
        "Framework :: Django"
    ],
    install_requires=['Django >= 3.1',
                      "requests",
                      'geopayment',
                      'loguru==0.7.0',
                      ]
)
