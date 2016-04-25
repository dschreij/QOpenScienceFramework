#!/usr/bin/env python

import os
import glob
import QOpenScienceFramework
from setuptools import setup

def files(path):
	l = [fname for fname in glob.glob(path) if os.path.isfile(fname) \
		and not fname.endswith('.pyc')]
	print(l)
	return l


def data_files():
	return [
		("QOpenScienceFramework",
			files("QOpenScienceFramework/*")),
		("QOpenScienceFramework/img",
			files("QOpenScienceFramework/img/*")),
		]

setup(
	name="python-qosf",
	version=QOpenScienceFramework.__version__,
	description="Qt widgets for the Open Science Framework",
	author=QOpenScienceFramework.__author__,
	author_email="dschreij@gmail.com",
	url="https://github.com/dschreij/QOpenScienceFramework",
	classifiers=[
		'Intended Audience :: Science/Research',
		'Topic :: Scientific/Engineering',
		'Environment :: MacOS X',
		'Environment :: Win32 (MS Windows)',
		'Environment :: X11 Applications',
		'License :: OSI Approved :: Apache Software License',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 3',
	],
	install_requires=[
		'qtpy',
		'arrow',
		'humanize',
		'python-fileinspector',
		'requests_oauthlib',
		'qtawesome',
	],
	include_package_data=False,
	packages = ['QOpenScienceFramework'],
	data_files=data_files()
	)
print(data_files())