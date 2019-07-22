![Install with conda](https://anaconda.org/cogsci/python-qosf/badges/installer/conda.svg)
![Anaconda cloud](https://anaconda.org/cogsci/python-qosf/badges/version.svg)

# Open Science Framework - Python API toolkit
This repository should contain everything you need to start off with connecting your python application to the Open Science Framework (https://osf.io). It offers python functions that translate to Open Science Framework API endpoints, and also a set of PyQt widgets (should work with both pyqt4 and pyqt5 thanks to qtpy) that are designed to display and interact with information obtained through the OSF API.

![Widgets](https://dschreij.github.io/images/projects/OSFScreenshots.png)

# Installation

## Anaconda

The QOpenScienceFramework module is available in the Anaconda Python distribution and can be installed from the cogsci channel on anaconda.org. To add cogsci to your list of channels to track and be assured of future updates, issue the command

    conda config --add channels cogsci

You can then install the QOpenScienceFramework module and all its dependencies with the single command

    conda install python-qosf

## Pypi

It is also possible to install the module using pip

    pip install python-qosf

This should also install the dependencies this project depends on (except pyqt)

## Manual installation

You can of course also instal the module from source by using the supplied setup.py script but then you also have to manually install all modules that QOpenScienceFramework depends on.

Clone this repository by issuing

    git clone https://github.com/dschreij/QOpenScienceFramework.git

and then run

    python setup.py install

Make sure you have the following modules available (all should be easy to get with anaconda and/or pip)

- pyqt4 or pyqt5 (https://www.riverbankcomputing.com/software/pyqt/intro)
- qtpy (https://github.com/spyder-ide/qtpy)
- qtawesome (https://github.com/spyder-ide/qtawesome)
- requests_oauthlib (https://github.com/requests/requests-oauthlib)
- fileinspector (https://github.com/dschreij/fileinspector)
- arrow (http://crsmithdev.com/arrow/)
- humanize (https://pypi.python.org/pypi/humanize)
- python-magic (optional)

## Test
If you have all above modules installed, you should be able to perform a test run with

    python example.py

This should load and display all widgets that can be used.

## Documentation

Documentation can be found at <http://dschreij.github.io/QOpenScienceFramework>
