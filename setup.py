#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Author  :   windpro
E-mail  :   windprog@gmail.com
Date    :   15/8/26
Desc    :   
"""
from setuptools import setup

VERSION = '0.1'

setup(
    name='tun-tunnel-control',
    version=VERSION,
    author='',
    author_email='',
    packages=[
        'tun_tunnel',
    ],
    install_requires=[
        'qingcloud-sdk',
    ],
)
