# -*- coding: utf-8 -*-
"""
@author: Daniel Schreij

This module is distributed under the Apache v2.0 License.
You should have received a copy of the Apache v2.0 License
along with this module. If not, see <http://www.apache.org/licenses/>.
"""
# Python3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Import basics
import sys
import os
import json
import time
import logging
logging.basicConfig(level=logging.INFO)

# Required QT classes
import qtpy
qtpy.setup_apiv2()
from qtpy import QtWidgets, QtCore
# Widgets
from openscienceframework import widgets
# Event dispatcher and listeners
from openscienceframework.manager import ConnectionManager, TestListener, TokenFileListener

class StandAlone(object):

	def __init__(self):
		tokenfile = os.path.abspath("token.json")
		# Create manager object
		self.manager = ConnectionManager(tokenfile)

		# Init and set up user badge
		self.user_badge = widgets.UserBadge(self.manager)
		self.user_badge.move(850,100)

		# Set-up project tree
		project_tree = widgets.ProjectTree(self.manager, use_theme="Faenza")

		# Init and set up Project explorer
		self.project_explorer = widgets.OSFExplorer(self.manager, tree_widget=project_tree)
		self.project_explorer.move(50,100)

		# Testlistener (to be removed later). Simply prints out which event
		# it received.
		self.tl = TestListener()

		# Token file listener writes the token to a json file if it receives
		# a logged_in event and removes this file after logout
		# Filename of the file to store token information in.
		
		self.tfl = TokenFileListener(tokenfile)

		self.manager.dispatcher.add_listeners([self.tl, self.tfl, self.user_badge, self.project_explorer])

		# Connect click on user badge logout button to osf logout action
		self.user_badge.logout_request.connect(self.manager.logout)
		self.user_badge.login_request.connect(self.manager.login)

		# If a valid token is stored in token.json, use that.
		# Otherwise show the loging window.
		
		self.manager.login()
		self.user_badge.show()
		self.project_explorer.show()
		self.manager.get_logged_in_user()

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)

	print(QtCore.QT_VERSION_STR)

	# Enable High DPI display with PyQt5
	if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
		app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

	test = StandAlone()
	exitcode = app.exec_()
	logging.info("App exiting with code {}".format(exitcode))
	sys.exit(exitcode)



