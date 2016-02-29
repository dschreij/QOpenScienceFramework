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
from qtpy import QtWidgets, QtCore

# Oauth2 connection to OSF
from openscienceframework import connection as osf

# Widgets
from openscienceframework import widgets

# Event dispatcher and listeners
from openscienceframework.util import EventDispatcher, TestListener, TokenFileListener

class StandAlone(object):
	
	def __init__(self):
		# Init browser in which login page is displayed
		self.browser = widgets.LoginWindow()
		
		# Init and set up user badge
		self.user_badge = widgets.UserBadge()
		self.user_badge.move(850,100)
		self.user_badge.show()
		
		# Init and set up Project explorer
		self.project_explorer = widgets.ProjectExplorer()
		self.project_explorer.move(50,100)
		self.project_explorer.show()
	
		# Create event dispatcher
		self.dispatcher = EventDispatcher()
		
		# Filename of the file to store token information in.
		self.tokenfile = "token.json"	
		
		# Connect OSF logged_in callback function to EventDispatcher	
		osf.logged_in = self.dispatcher.dispatch_login
		# Connect OSF logged_out callback function to EventDispatcher
		osf.logged_out = self.dispatcher.dispatch_logout
		
		# Testlistener (to be removed later). Simply prints out which event
		# it received.
		tl = TestListener()
		# Token file listener writes the token to a json file if it receives
		# a logged_in event and removes this file after logout
		tfl = TokenFileListener(self.tokenfile, osf)
		self.dispatcher.add([self.user_badge, self.project_explorer, tl, tfl])
		
		# Connect click on user badge logout button to osf logout action
		self.user_badge.logout_request.connect(osf.logout)
		self.user_badge.login_request.connect(self.show_login_window)
		
		# If a valid token is stored in token.json, use that.
		# Otherwise show the loging window.
		if not self.check_for_stored_token():
			self.show_login_window()
		else:
			self.dispatcher.dispatch("login")
		
	def check_for_stored_token(self):
		""" Checks if valid token information is stored in a token.json file.
		of the project root. If not, or if the token is invalid/expired, it returns
		False"""
		
		if os.path.isfile(self.tokenfile):
			with open(self.tokenfile,"r") as f:
				token = json.loads(f.read())
				
			# Check if token has not yet expired
			if token["expires_at"] > time.time():
				# Load the token information in the session object, but check its
				# validity!
				osf.session.token = token
				# See if a request succeeds without errors
				try:
					osf.get_logged_in_user()
					return True
				except osf.TokenError as e:
					logging.error(e)
					osf.reset_session()
					os.remove(self.tokenfile)
			else:
				logging.info("Token expired; need log-in")
		return False
		
	def show_login_window(self):
		""" Show the QWebView window with the login page of OSF """
		auth_url, state = osf.get_authorization_url()
		logging.info("Generated authorization url: {}".format(auth_url))
		# Set up browser
		browser_url = QtCore.QUrl(auth_url)
		self.browser.load(browser_url)
		self.browser.show()
		
if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	
	# Enable High DPI display with PyQt5
	if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
		app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
								
	test = StandAlone()
	exitcode = app.exec_()
	logging.info("App exiting with code {}".format(exitcode))
	sys.exit(exitcode)



