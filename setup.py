#!/usr/bin/env python

import os

from setuptools import setup


def readreq(filename):
    result = []
    with open(filename) as f:
        for req in f:
            req = req.lstrip()
            if req.startswith('-e ') or req.startswith('http:'):
                idx = req.find('#egg=')
                if idx >= 0:
                    req = req[idx + 5:].partition('#')[0].strip()
                else:
                    pass
            else:
                req = req.partition('#')[0].strip()
            if not req:
                continue
            result.append(req)
    return result


def readfile(filename):
    with open(filename) as f:
        return f.read()


setup(
    name='fstree',
    version='0.1.0',
    author='Kevin L. Mitchell',
    author_email='klmitch@mit.edu',
    url='https://github.com/klmitch/fstree',
    description="File System Tree",
    long_description=readfile('README.rst'),
    license='Apache License (2.0)',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    packages=['fstree'],
    install_requires=readreq('requirements.txt'),
    tests_require=readreq('test-requirements.txt'),
)
