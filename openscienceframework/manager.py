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
import inspect
import time
import logging
import os
import json

#OSF modules
import openscienceframework.connection as osf
from openscienceframework import widgets

# PyQt modules
from qtpy import QtCore, QtNetwork, QtWidgets
import qtpy
qtpy.setup_apiv2()

class ConnectionManager(QtNetwork.QNetworkAccessManager):
	"""
	The connection manager does much of the heavy lifting in communicating with the
	OSF. It checks if the app is still authorized to send requests, and also checks
	for responses indicating this is not the case."""

	def __init__(self, tokenfile="token.json", **kwargs):
		""" Constructor """
		super(ConnectionManager, self).__init__()
		self.tokenfile = tokenfile
		self.dispatcher = EventDispatcher()

		# Init browser in which login page is displayed
		self.browser = widgets.LoginWindow()
		# Connect browsers logged in event to that of dispatcher's
		self.browser.logged_in.connect(self.dispatcher.dispatch_login)

	def get_QUrl(self, url):
		""" Qt4 doesn url handling a bit different than Qt5, so check for that
		here."""
		if QtCore.QT_VERSION_STR < '5':
			return QtCore.QUrl.fromEncoded(url)
		else:
			return QtCore.QUrl(url)

	# -------------------- Login and Logout functions -----------------------------

	def login(self):
		# If a valid stored token is found, read that in an dispatch login event
		if self.check_for_stored_token(self.tokenfile):
			self.dispatcher.dispatch_login()
			return
		
		# Otherwise, do the whole authentication dance
		""" Show the QWebView window with the login page of OSF """
		auth_url, state = osf.get_authorization_url()

		# Set up browser
		browser_url = self.get_QUrl(auth_url)
		
		self.browser.load(browser_url)
		self.browser.show()

	def logout(self):
		""" Logout from OSF """
		if osf.logout():
			self.dispatcher.dispatch_logout()

	def check_for_stored_token(self, tokenfile):
		""" Checks if valid token information is stored in a token.json file.
		of the project root. If not, or if the token is invalid/expired, it returns
		False"""
		logging.info("Looking for token at {}".format(tokenfile))
		if tokenfile is None:
			tokenfile = self.tokenfile

		if not os.path.isfile(tokenfile):
			return False

		with open(tokenfile,"r") as f:
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
				os.remove(tokenfile)
		else:
			logging.info("Token expired; need log-in")
			return False

	# -------------------- Communication with OSF API -----------------------------'
	def get(self, url):
		qurl = self.get_QUrl(url)
		request = QtNetwork.QNetworkRequest(qurl)
		if osf.is_authorized():
			name = "Bearer"
			value = osf.session.token
			request.setRawHeader(name, value)
		return super(ConnectionManager, self).get(request)
	
	def get_logged_in_user(self):
		api_call = osf.api_call("logged_in_user")
		return self.get(api_call)

	def get_user_projects(self):
		api_call = self.get_QUrl(osf.api_call("projects"))

	def get_project_repos(self, project_id):
		api_call = self.get_QUrl(osf.api_call("project_repos",project_id))

	def get_repo_files(self, project_id, repo_name):
		api_call = self.get_QUrl(osf.api_call("repo_files",project_id, repo_name))
		
	

class EventDispatcher(QtCore.QObject):
	""" This class fires events to connected classes, which are henceforth
	referenced to as 'listeners'.
	Basically EventDispatcher's purpose is to propagate login and logout events
	to the QWidget subclasses that require authorization at the OSF to function
	correctly, but of course this can be extended with events that are relevant
	for all listeners.

	The only requirement for listener classes is that they implement a handling
	function for each event that should be named "handle_<event_name>". For example, to catch
	a login event, a listener should have the function handle_login."""

	# List of possible events this dispatcher can emit
	logged_in = QtCore.pyqtSignal()
	logged_out = QtCore.pyqtSignal()

	def init(self, *args, **kwargs):
		super(EventDispatcher, self).__init__(*args, **kwargs)

	def add_listeners(self, obj_list):
		""" Add (a) new object(s) to the list of objects listening for the events

		Parameters
		----------
		obj : object
			the list of listeners to add. Listeners should implement handling \
			functions which are called when certain events occur.
			The list of functions that listeners should implement is currently:

				- handle_login
				- handle_logout
		"""
		# If the object passed is a list, add all object in the list
		if not type(obj_list) is list:
			raise ValueError("List expected; {} received".format(type(obj_list)))

		for item in obj_list:
			self.add_listener(item)
		return self

	def add_listener(self, item):
		""" Add a new object to listen for the events

		Parameters
		----------
		obj : object
			the listener to add. Should implement handling functions which are
			called when certain events occur. The list of functions that the
			listener should implement is currently:

				- handle_login
				- handle_logout
		"""
		logging.info("Linking {}".format(item))
		if not hasattr(item,"handle_login"):
			raise AttributeError("The passed item {} does not have the required 'handle_login' function".format(item))
		self.logged_in.connect(item.handle_login)
		if not hasattr(item,"handle_logout"):
			raise AttributeError("The passed item {} does not have the required 'handle_logout' function".format(item))
		self.logged_out.connect(item.handle_logout)

	def remove_listener(self, item):
		""" Remove a listener.

		obj : object
			The object that is to be disconnected

		Returns
		-------
		A reference to the current instance of this object (self)."""
		self.logged_in.disconnect(item.handle_login)
		self.logged_out.disconnect(item.handle_logout)
		return self

	def dispatch_login(self):
		""" Convenience function to dispatch the login event """
		self.logged_in.emit()

	def dispatch_logout(self):
		""" Convenience function to dispatch the logout event """
		self.logged_out.emit()

class TestListener(QtWidgets.QWidget):
	def __init__(self):
		super(TestListener,self).__init__()

	def handle_login(self):
		print("Handling login!")
		logging.info("Login event received")

	def handle_logout(self):
		logging.info("Logout event received")

class TokenFileListener(object):
	""" This listener stores the OAuth2 token after login and destroys it after
	logout."""
	def __init__(self,tokenfile):
		super(TokenFileListener,self).__init__()
		self.tokenfile = tokenfile

	def handle_login(self):
		if osf.session.token:
			tokenstr = json.dumps(osf.session.token)
			logging.info("Writing token file to {}".format(self.tokenfile))
			with open(self.tokenfile,'w') as f:
				f.write(tokenstr)
		else:
			logging.error("Error, could not find authentication token")

	def handle_logout(self):
		if os.path.isfile(self.tokenfile):
			try:
				os.remove(self.tokenfile)
			except Exception as e:
				logging.warning("WARNING: {}".format(e.message))


if __name__== "__main__":
	print ("Test the dispatcher.")
	dispatcher = ConnectionManager()
	tl = TestListener() # To be removed later
	dispatcher.add(tl)

	for event in dispatcher.events:
		dispatcher.dispatch(event)
