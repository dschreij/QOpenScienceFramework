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
import logging
import tempfile
logging.basicConfig(level=logging.INFO)

# Required QT classes
from qtpy import QtWidgets, QtCore
# Widgets
from QOpenScienceFramework import widgets, events
from QOpenScienceFramework import connection as osf
# Event dispatcher and listeners
from QOpenScienceFramework.manager import ConnectionManager
from QOpenScienceFramework.compat import *

####### CONFIGURE THE CLIENT ID AND REDIRECT URI HERE. REGISTER AT OSF.IO ######
client_id = "878e88b88bf74471a6a3ff05e007b0dd" # "<YOUR_CLIENT_ID_HERE>"
redirect_uri = "https://www.getpostman.com/oauth2/callback" # "<YOUR_REDIRECT_URI_HERE>"
################################################################################

class InvalidateButton(QtWidgets.QWidget):
	""" Just a button to tamper with the OSF session and see what the app does
	to recover from missing authentication information """

	def __init__(self, *args, **kwargs):
		super(InvalidateButton, self).__init__(*args, **kwargs)
		self.setLayout(QtWidgets.QHBoxLayout())
		pb = QtWidgets.QPushButton("Invalidate session")
		pb.clicked.connect(self.invalidate_session)
		self.layout().addWidget(pb)

	def invalidate_session(self):
		print("Invalidating session!")
		osf.session = osf.create_session()
		print(osf.session.token)

class StandAlone(object):
	""" Class that opens all available widgets when instantiated for testing
	purposes. """

	def __init__(self):
		# Check if client_id and redirect_uri have been changed
		if client_id == "<YOUR_CLIENT_ID_HERE>":
			raise RuntimeError("Please enter the client_id you have registered"
				" for your app at the OSF")
		if redirect_uri == "<YOUR_REDIRECT_URI_HERE>":
			raise RuntimeError("Please enter the redirect uri you have registered"
				" for your app at the OSF")

		# Set OSF server settings
		server_settings = {
		 	"client_id"		: client_id,
			"redirect_uri"	: redirect_uri,
		}
		# Add these settings to the general settings
		osf.settings.update(server_settings)
		osf.create_session()

		tmp_dir = safe_decode(tempfile.gettempdir())
		tokenfile = os.path.join(tmp_dir, u"osf_token.json")
		# Create manager object
		self.manager = ConnectionManager(tokenfile=tokenfile)

		# Init and set up user badge
		self.user_badge = widgets.UserBadge(self.manager)
		self.user_badge.move(850, 100)

		# Set-up project tree
		project_tree = widgets.ProjectTree(self.manager, use_theme="Faenza")

		# Init and set up Project explorer
		self.project_explorer = widgets.OSFExplorer(
			self.manager, tree_widget=project_tree
		)
		self.project_explorer.move(50, 100)

		# Token file listener writes the token to a json file if it receives
		# a logged_in event and removes this file after logout
		# Filename of the file to store token information in.
		self.tfl = events.TokenFileListener(tokenfile)

		self.manager.dispatcher.add_listeners(
			[
				self.manager, self.tfl, project_tree,
				self.user_badge, self.project_explorer
			]
		)
		# Connect click on user badge logout button to osf logout action
		self.user_badge.logout_request.connect(self.manager.logout)
		self.user_badge.login_request.connect(self.manager.login)

		# self.ib = InvalidateButton()
		# self.ib.setGeometry(850,200,200,50)
		# self.ib.show()

		# If a valid token is stored in token.json, use that.
		# Otherwise show the login window.
		self.manager.login()
		# Show the user badge
		self.user_badge.show()
		self.project_explorer.show()

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)

	print("Using Qt {}".format(QtCore.QT_VERSION_STR))

	# Enable High DPI display with PyQt5
	if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
		app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

	test = StandAlone()
	exitcode = app.exec_()
	logging.info("App exiting with code {}".format(exitcode))
	sys.exit(exitcode)



