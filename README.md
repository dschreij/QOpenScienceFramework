<img src="https://anaconda.org/cogsci/python-qosf/badges/installer/conda.svg" width="50">
<img src="https://anaconda.org/cogsci/python-qosf/badges/version.svg" width="50">

# Open Science Framework - Python API toolkit
This repository should contain everything you need to start off with connecting your python application to the Open Science Framework (https://osf.io). It offers python functions that translate to Open Science Framework API endpoints, and also a set of PyQt widgets (should work with both pyqt4 and pyqt5 thanks to qtpy) that are designed to display and interact with information obtained through the OSF API.

## Installation
Make sure you have the following modules available (all should be easy to get with anaconda and/or pip)

- pyqt4 or pyqt5 (https://www.riverbankcomputing.com/software/pyqt/intro)
- qtpy (https://github.com/spyder-ide/qtpy)
- qtawesome (https://github.com/spyder-ide/qtawesome)
- requests_oauthlib (https://github.com/requests/requests-oauthlib)
- fileinspector (https://github.com/dschreij/fileinspector)
- arrow (http://crsmithdev.com/arrow/)
- humanize (https://pypi.python.org/pypi/humanize)
- python-magic (optional)

## Running
If you have all above modules installed, you should be able to perform a test run with

    python example.py

This should load and display all widgets that can be used.

More documentation will soon follow
