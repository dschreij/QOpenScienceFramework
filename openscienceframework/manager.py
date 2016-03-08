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
import logging
import os
import json
import time

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

	# The maximum number of allowed redirects
	MAX_REDIRECTS = 5

	def __init__(self, manager, tokenfile="token.json"):
		""" Constructor """
		super(ConnectionManager, self).__init__()
		self.manager = manager
		self.tokenfile = tokenfile
		self.dispatcher = EventDispatcher()

		# Init browser in which login page is displayed
		self.browser = widgets.LoginWindow()
		# Connect browsers logged in event to that of dispatcher's
		self.browser.logged_in.connect(self.dispatcher.dispatch_login)

		self.logged_in_user = {}

	def get_QUrl(self, url):
		""" Qt4 doesn url handling a bit different than Qt5, so check for that
		here."""
		if QtCore.QT_VERSION_STR < '5':
			return QtCore.QUrl.fromEncoded(url)
		else:
			return QtCore.QUrl(url)

	# --------------------- Login and Logout functions ---------------------------

	def login(self):
		""" Opens a browser window through which the user can log in. Upon successful
		login, the browser widgets fires the 'logged_in' event. which is caught by this object
		again in the handle_login() function. """

		# If a valid stored token is found, read that in an dispatch login event
		if self.check_for_stored_token(self.tokenfile):
			self.dispatcher.dispatch_login()
			return
		# Otherwise, do the whole authentication dance
		self.show_login_window()

	def show_login_window(self):
		""" Show the QWebView window with the login page of OSF """
		auth_url, state = osf.get_authorization_url()

		# Set up browser
		browser_url = self.get_QUrl(auth_url)
		
		self.browser.load(browser_url)
		self.browser.show()

	def logout(self):
		""" Logout from OSF """
		if osf.is_authorized() and osf.session.access_token:
			self.post(osf.logout_url, self.__logout_succeeded, {'token':osf.session.access_token})

	def __logout_succeeded(self,data,*args):
		self.dispatcher.dispatch_logout()

	def check_for_stored_token(self, tokenfile):
		""" Checks if valid token information is stored in a token.json file.
		of the project root. If not, or if the token is invalid/expired, it returns
		False"""

		logging.info("Looking for token at {}".format(tokenfile))

		if not os.path.isfile(tokenfile):
			return False

		try:
			token = json.load(open(tokenfile))
		except IOError:
			raise IOError("Token file could not be opened.")

		# Check if token has not yet expired
		if token["expires_at"] > time.time() :
			# Load the token information in the session object, but check its
			# validity!
			osf.session.token = token
			# See if a request succeeds without errors
			try:
				osf.get_logged_in_user()
				return True
			except osf.TokenExpiredError as e:
				osf.reset_session()
				os.remove(tokenfile)
				self.show_login_window()
		else:
			logging.info("Token expired; need log-in")
			return False

	# ------------------------ Communication with OSF API ---------------------------'
	def get(self, url, callback, *args):
		""" Perform a HTTP GET request. The OAuth2 token is automatically added to the
		header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url to perform the get request on
		callback : function
			The function to call once the request is finished.
		*args (optional)
			Any other arguments that you want to have passed to callable
		"""

		# First do some checking of the passed arguments
		if not type(url) in [str, QtCore.QUrl]:
			raise TypeError("url should be a string or QUrl object")

		if not callable(callback):
			raise TypeError("callback should be a function or callable.")

		if type(url) is str:
			url = self.get_QUrl(url)

		request = QtNetwork.QNetworkRequest(url)
		if osf.is_authorized():
			name = "Authorization".encode()
			value = ("Bearer {}".format(osf.session.access_token)).encode()
			request.setRawHeader(name, value)

		self.redirect_counter = 0
		reply = super(ConnectionManager, self).get(request)
		reply.finished.connect(lambda: self.slotFinished(callback, *args))

	def post(self, url, callback, data_to_send, *args):
		""" Perform a HTTP POST request. The OAuth2 token is automatically added to the
		header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url to perform the get request on.
		callback : function
			The function to call once the request is finished.
		data_to_send : dict
			The data to send with the POST request. keys will be used as variable names
			and values will be used as the variable values.
		*args (optional)
			Any other arguments that you want to have passed to callable.
		"""
		# First do some checking of the passed arguments
		if not type(url) in [str, QtCore.QUrl]:
			raise TypeError("url should be a string or QUrl object")

		if not callable(callback):
			raise TypeError("callback should be a function or callable.")

		if not type(data_to_send) is dict:
			raise TypeError("The POST data should be passed as a dict")

		if not type(url) is QtCore.QUrl:
			url = self.get_QUrl(url)
		request = QtNetwork.QNetworkRequest(url)

		request.setHeader(request.ContentTypeHeader,"application/x-www-form-urlencoded");

		if osf.is_authorized():
			name = "Authorization".encode()
			value = ("Bearer {}".format(osf.session.access_token)).encode()
			request.setRawHeader(name, value)
		
		# Sadly, Qt4 and Qt5 show some incompatibility in that QUrl no longer has the
		# addQueryItem function in Qt5. This has moved to a differen QUrlQuery object
		if QtCore.QT_VERSION_STR < '5':
			postdata = QtCore.QUrl()
		else:
			postdata = QtCore.QUrlQuery()
		# Add data
		for varname in data_to_send:
			postdata.addQueryItem(varname, data_to_send.get(varname))
		# Convert to QByteArray for transport
		if QtCore.QT_VERSION_STR < '5':
			final_postdata = postdata.encodedQuery()
		else:
			final_postdata = postdata.toString(QtCore.QUrl.FullyEncoded).encode()
		# Fire!
		reply = super(ConnectionManager, self).post(request, final_postdata)
		reply.finished.connect(lambda: self.slotFinished(callback, *args))

	def get_logged_in_user(self, callback):
		""" Contact the OSF to request data of the currently logged in user

		Parameters
		----------
		callback : function
			The callback function to which the data should be delivered

		"""
		api_call = osf.api_call("logged_in_user")
		self.get(api_call, callback)

	def get_user_projects(self, callback):
		api_call = osf.api_call("projects")
		self.get(api_call, callback)

	def get_project_repos(self, project_id, callback):
		api_call = osf.api_call("project_repos",project_id)
		self.get(api_call, callback)

	def get_repo_files(self, project_id, repo_name, callback):
		api_call = osf.api_call("repo_files",project_id, repo_name)
		self.get(api_call, callback)

	# ----------------------------- PyQt Slots --------------------------------'

	def slotFinished(self, callback, *args):
		reply = self.sender()
		request = reply.request()
		
		# If an error occured, just show a simple QMessageBox for now
		if reply.error() != reply.NoError:
			QtWidgets.QMessageBox.critical(None, 
				str(reply.attribute(request.HttpStatusCodeAttribute)), 
				reply.errorString()
			)
			return
		
		# Check if the reply indicates a redirect
		if reply.attribute(request.HttpStatusCodeAttribute) in [301,302]:
			# To prevent endless redirects, make a count of them and only
			# allow a set maximum
			if self.redirect_counter < self.MAX_REDIRECTS:
				self.redirect_counter += 1
			else:
				QtWidgets.QMessageBox.critical(None, 
					"Whoops, something is going wrong", 
					"Too Many redirects"
				)
				reply.deleteLater()
				return
			# Perform another request with the redirect_url and pass on the callback
			redirect_url = reply.attribute(request.RedirectionTargetAttribute)
			self.get(redirect_url, callback, *args)
		else:
			# Content is a QByteArray, pass it on as a string for easier usage
			callback(reply.readAll(), *args)

		# Cleanup, mark the request and reply objects for deletion
		reply.deleteLater()

	def handle_login(self):
		self.get_logged_in_user(self.set_logged_in_user)

	def handle_logout(self):
		self.osf.reset_session()
		self.logged_in_user = {}

	# ----------------------------- Other callbacks --------------------------------'

	def set_logged_in_user(self, user_data):
		""" Callback function - Locally saves the data of the currently logged_in user """
		self.logged_in_user = json.loads(user_data.data().decode())
		

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
				logging.info("Deleted {}".format(self.tokenfile))
			except Exception as e:
				logging.warning("WARNING: {}".format(e.message))


if __name__== "__main__":
	print ("Test the dispatcher.")
	dispatcher = ConnectionManager()
	tl = TestListener() # To be removed later
	dispatcher.add(tl)

	for event in dispatcher.events:
		dispatcher.dispatch(event)
