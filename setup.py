#! /usr/bin/env python2


from setuptools import setup


setup(
    name='aafilters',
    version='0.1a1',
    author='Alexandre Leray, Eric Schrijver, The Active Archive Contributors',
    author_email='alexandre@stdin.fr, eric@ericschrijver.nl',
    description=('Dynamically cache and process HTTP ressources'),
    url='https://github.com/aleray/aafilters',
    packages=[
        'aafilters',
        'aafilters.fallback'
    ],
    include_package_data = True,
    install_requires=[
        'requests==2.0.1',
        'Pillow==2.2.1',
        'python-magic>=0.4,<0.5'
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'Programming Language :: Python',
    ]
)
