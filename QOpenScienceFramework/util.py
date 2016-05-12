# -*- coding: utf-8 -*-
"""
Utility functions and classes used throughout the module
"""

import os
from qtpy import QtWidgets, QtGui, QtCore

def check_if_opensesame_file(filename, os3_only=False):
	""" Checks if the passed file is an OpenSesame file, based on its extension.

	Parameters
	----------
	filename : string
		The file to check
	os3_only : bool (default: False)
		Only check for the newer .osexp files (from OpenSesasme 3 on), if this
		parameter is set to True, this function will return False for legacy
		.opensesame and .opensesame.tar.gz formats

	Returns
	-------
	boolean :
		True if filename is an OpenSesame file, False if not
	"""
	ext = os.path.splitext(filename)[1]
	if os3_only:
		return ext == '.osexp'

	if ext in ['.osexp', '.opensesame'] or \
		(ext == '.gz' and 'opensesame.tar.gz' in filename):
		return True
	return False

class QElidedLabel(QtWidgets.QLabel):
	""" Label that elides its contents by overwriting paintEvent"""
	def paintEvent(self, event):
		painter = QtGui.QPainter(self)
		metrics = QtGui.QFontMetrics(self.font())
		elided = metrics.elidedText(self.text(), QtCore.Qt.ElideRight, self.width())
		painter.drawText(self.rect(), self.alignment(), elided)

__all__ = ['check_if_opensesame_file', 'QElidedLabel']