#!/usr/bin/env python
from setuptools import setup

with open("README.rst") as f:
    readme = f.read()

setup(
    name="georgian-django-payments",
    author="graey",
    version='1.0',
    author_email="info@graey.ge",
    description="Georgian Payments",
    setup_requires=["setuptools_scm"],
    url="https://github.com/graey-ge/georgian-django-payments",
    packages=['payments'],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django :: 2.2",
        "Framework :: Django :: 3.0",
        "Framework :: Django :: 3.1",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Django",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=['Django >= 3.1',
                      "requests",
                      'geopayment>=0.6.3',
                      'loguru==0.7.0',
                      ]
)
