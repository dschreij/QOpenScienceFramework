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
import logging
import os
import json
import time

#OSF modules
import openscienceframework.connection as osf
from openscienceframework import widgets, events

# Easier function decorating
from functools import wraps

# PyQt modules
from qtpy import QtCore, QtNetwork, QtWidgets
import qtpy
qtpy.setup_apiv2()

# Python 2 and 3 compatiblity settings
from openscienceframework.compat import *

class ConnectionManager(QtNetwork.QNetworkAccessManager):
	"""
	The connection manager does much of the heavy lifting in communicating with the
	OSF. It checks if the app is still authorized to send requests, and also checks
	for responses indicating this is not the case."""

	# The maximum number of allowed redirects
	MAX_REDIRECTS = 5
	error_message = QtCore.pyqtSignal('QString','QString')
	info_message = QtCore.pyqtSignal('QString','QString')

	def __init__(self, manager, tokenfile="token.json"):
		""" Constructor """
		super(ConnectionManager, self).__init__()
		self.manager = manager
		self.tokenfile = tokenfile
		self.dispatcher = events.EventDispatcher()

		# Notifications
		self.notifier = events.Notifier()
		self.error_message.connect(self.notifier.error)
		self.info_message.connect(self.notifier.info)

		# Init browser in which login page is displayed
		self.browser = widgets.LoginWindow()
		# Connect browsers logged in event to that of dispatcher's
		self.browser.logged_in.connect(self.dispatcher.dispatch_login)

		self.logged_in_user = {}

	#--- Login and Logout functions

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
		browser_url = get_QUrl(auth_url)

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
			except osf.TokenExpiredError:
				osf.reset_session()
				os.remove(tokenfile)
				self.show_login_window()
		else:
			logging.info("Token expired; need log-in")
			return False

	#--- Communication with OSF API

	def check_network_accessibility(func):
		""" Checks if network is accessible """
		@wraps(func)
		def func_wrapper(inst, *args, **kwargs):
			if inst.networkAccessible() == inst.NotAccessible:
				self.error_message.emit(
					"No network access",
					"Your network connection is down or you currently have"
					" no Internet access."
				)
				return
			else:
				return func(inst, *args, **kwargs)
		return func_wrapper

	@check_network_accessibility
	def get(self, url, callback, *args, **kwargs):
		""" Perform a HTTP GET request. The OAuth2 token is automatically added to the
		header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url to perform the get request on
		callback : function
			The function to call once the request is finished successfully.
		downloadProgess : function (defualt: None)
			The slot (callback function) for the downloadProgress signal of the
			reply object. This signal is emitted after a certain amount of bytes
			is received, and can be used for instance to update a download progress
			dialog box. The callback function should have two parameters to which
			the transfered and total bytes can be assigned.
		readyRead : function (default : None)
			The slot (callback function) for the readyRead signal of the
			reply object.
		errorCallback : function (default: None)
			function to call whenever an error occurs. Should be able to accept
			the reply object as an argument.
		progressDialog : QtWidgets.QProgressDialog (default: None)
			The dialog to send the progress indication to. Will be included in the
			reply object so that it is accessible in the downloadProgress slot, by
			calling self.sender().property('progressDialog')
		*args (optional)
			Any other arguments that you want to have passed to the callback
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback
		"""
		# First do some checking of the passed arguments

		if not type(url) == QtCore.QUrl and not isinstance(url, basestring):
			raise TypeError("url should be a string or QUrl object")

		if not callable(callback):
			raise TypeError("callback should be a function or callable.")

		if not type(url) is QtCore.QUrl:
			url = get_QUrl(url)

		request = QtNetwork.QNetworkRequest(url)

		# Check if this is a redirect and keep a count to prevent endless
		# redirects. If redirect_count is not set, init it to 0
		kwargs['redirect_count'] = kwargs.get('redirect_count',0)

		if osf.is_authorized():
			name = "Authorization".encode()
			value = ("Bearer {}".format(osf.session.access_token)).encode()
			request.setRawHeader(name, value)

		reply = super(ConnectionManager, self).get(request)

		# Check if a QProgressDialog has been passed to which the download status
		# can be reported. If so, add it as a property of the reply object
		dlpDialog = kwargs.get('progressDialog', None)
		if isinstance(dlpDialog, QtWidgets.QProgressDialog):
			dlpDialog.canceled.connect(reply.abort)
			reply.setProperty('dlpDialog', dlpDialog)

		# Check if a callback has been specified to which the downloadprogress
		# is to be reported
		dlpCallback = kwargs.get('downloadProgress', None)
		if callable(dlpCallback):
			reply.downloadProgress.connect(dlpCallback)

		# Check if a callback has been specified for reply's readyRead() signal
		# which emits as soon as data is available on the buffer and doesn't wait
		# till the whole transfer is finished as the finished() callback does
		# This is useful when downloading larger files
		rrCallback = kwargs.get('readyRead', None)
		if callable(rrCallback):
			reply.readyRead.connect(
				lambda: rrCallback(*args, **kwargs)
			)

		reply.finished.connect(
			lambda: self.__get_finished(
				callback, *args, **kwargs
			)
		)
		return reply

	@check_network_accessibility
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
		if not type(url) == QtCore.QUrl and not isinstance(url, basestring):
			raise TypeError("url should be a string or QUrl object")

		if not callable(callback):
			raise TypeError("callback should be a function or callable.")

		if not type(data_to_send) is dict:
			raise TypeError("The POST data should be passed as a dict")

		if not type(url) is QtCore.QUrl:
			url = get_QUrl(url)

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
		reply.finished.connect(lambda: self.__slotFinished(callback, *args))

	def get_logged_in_user(self, callback):
		""" Contact the OSF to request data of the currently logged in user

		Parameters
		----------
		callback : function
			The callback function to which the data should be delivered once the
			request is finished

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong

		Note :
			To process retrieved data from this reply, the callback function
			argument should be used, and not the QNetworkReply object that is
			returned here.
		"""
		api_call = osf.api_call("logged_in_user")
		return self.get(api_call, callback)

	def get_user_projects(self, callback):
		""" Get a list of projects owned by the currently logged in user from OSF

		Parameters
		----------
		callback : function
			The callback function to which the data should be delivered once the
			request is finished

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong

		Note :
			To process retrieved data from this reply, the callback function
			argument should be used, and not the QNetworkReply object that is
			returned here.
		"""
		api_call = osf.api_call("projects")
		return self.get(api_call, callback)

	def get_project_repos(self, project_id, callback):
		""" Get a list of repositories from the OSF that belong to the passed
		project id

		Parameters
		----------
		project_id : string
			The project id that OSF uses for this project (e.g. the node id)
		callback : function
			The callback function to which the data should be delivered once the
			request is finished

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong

		Note :
			To process retrieved data from this reply, the callback function
			argument should be used, and not the QNetworkReply object that is
			returned here.
		"""
		api_call = osf.api_call("project_repos", project_id)
		return self.get(api_call, callback)

	def get_repo_files(self, project_id, repo_name, callback):
		""" Get a list of files from the OSF that belong to the indicated
		repository of the passed project id

		Parameters
		----------
		project_id : string
			The project id that OSF uses for this project (e.g. the node id)
		repo_name : string
			The repository to get the files from. Should be something along the
			lines of osfstorage, github, dropbox, etc. Check OSF documentation
			for a full list of specifications.
		callback : function
			The callback function to which the data should be delivered once the
			request is finished

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong

		Note :
			To process retrieved data from this reply, the callback function
			argument should be used, and not the QNetworkReply object that is
			returned here.
		"""
		api_call = osf.api_call("repo_files",project_id, repo_name)
		return self.get(api_call, callback)

	def download_file(self, url, destination, *args, **kwargs):
		""" Download a file by a using HTTP GET request. The OAuth2 token is automatically
		added to the header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url to perform the get request on
		destination : string
			The path and filename with which the file should be saved.
		finished_callback : function (default: None)
			The function to call once the download is finished.
		downloadProgress : function (default: None)
			The slot (callback function) for the downloadProgress signal of the
			reply object. This signal is emitted after a certain amount of bytes
			is received, and can be used for instance to update a download progress
			dialog box. The callback function should have two parameters to which
			the transfered and total bytes can be assigned.
		errorCallback : function (default: None)
			function to call whenever an error occurs. Should be able to accept
			the reply object as an argument.
		progressDialog : QtWidgets.QProgressDialog (default : None)
			The dialog to send the progress indication to. Will be included in the
			reply object so that it is accessible from the downloadProgress slot
		"""

		# Check if destination is a string
		if not type(destination) == str:
			raise ValueError("destination should be a string")
		# Check if the specified folder exists. However, because a situation is possible in which
		# the user has selected a destination but deletes the folder in some other program in the meantime,
		# show a message box, but do not raise an exception, because we don't want this to completely crash
		# our program.
		if not os.path.isdir(os.path.split(os.path.abspath(destination))[0]):
			self.error_message.emit(_("{} is not a valid destination").format(destination))
			return
		kwargs['destination'] = destination

		# Create tempfile
		tmp_file = QtCore.QTemporaryFile()
		tmp_file.open(QtCore.QIODevice.WriteOnly)
		kwargs['tmp_file'] = tmp_file

		# Callback function for when bytes are received
		kwargs['readyRead'] = self.__download_readyRead
		self.get(url, self.__download_finished, *args, **kwargs)

	#--- PyQt Slots

	def __get_finished(self, callback, *args, **kwargs):
		reply = self.sender()
		request = reply.request()

		errorCallback = kwargs.get('errorCallback', None)

		# If an error occured, just show a simple QMessageBox for now
		if reply.error() != reply.NoError:
			# User not authenticated to perform this request
			# Show login window again
			if reply.error() == reply.ContentAccessDenied:
				self.dispater.dispatch_logout()
				self.show_login_window()
				if callable(errorCallback):
					errorCallback(reply)
				reply.deleteLater()
				return

			self.error_message.emit(
				str(reply.attribute(request.HttpStatusCodeAttribute)),
				reply.errorString()
			)

			if callable(errorCallback):
				errorCallback(reply)
			reply.deleteLater()
			return

		# Check if the reply indicates a redirect
		if reply.attribute(request.HttpStatusCodeAttribute) in [301,302]:
			# To prevent endless redirects, make a count of them and only
			# allow a preset maximum
			if kwargs['redirect_count'] < self.MAX_REDIRECTS:
				kwargs['redirect_count'] += 1
			else:
				self.error_message.emit(
					_("Whoops, something is going wrong"),
					_("Too Many redirects")
				)
				if callable(errorCallback):
					errorCallback(reply)
				reply.deleteLater()
				return
			# Perform another request with the redirect_url and pass on the callback
			redirect_url = reply.attribute(request.RedirectionTargetAttribute)
#			logging.info("{} Redirect ({}) to {}".format(
#				reply.attribute(request.HttpStatusCodeAttribute),
#				kwargs['redirect_count'],
#				reply.attribute(request.RedirectionTargetAttribute).toString()
#			))
			self.get(redirect_url, callback, *args, **kwargs)
		else:
			# Remove some potentially internally used kwargs before passing
			# data on to the callback
			kwargs.pop('redirect_count', None)
			kwargs.pop('downloadProgress', None)
			kwargs.pop('readyRead', None)
			kwargs.pop('errorCallback', None)
			callback(reply, *args, **kwargs)

		# Cleanup, mark the reply object for deletion
		reply.deleteLater()

	def __download_readyRead(self, *args, **kwargs):
		reply = self.sender()
		data = reply.readAll()
		if not 'tmp_file' in kwargs or not isinstance(kwargs['tmp_file'], QtCore.QTemporaryFile):
			raise AttributeError('Missing file handle to write to')
		kwargs['tmp_file'].write(data)

	def __download_finished(self, reply, *args, **kwargs):
		# Do some checks to see if the required data has been passed.
		if not 'destination' in kwargs:
			raise AttributeError("No destination passed")
		if not 'tmp_file' in kwargs or not isinstance(kwargs['tmp_file'], QtCore.QTemporaryFile):
			raise AttributeError("No valid reference to temp file where data was saved")

		kwargs['tmp_file'].close()
		# If a file with the same name already exists at the location, try to
		# delete it.
		if QtCore.QFile.exists(kwargs['destination']):
			if not QtCore.QFile.remove(kwargs['destination']):
				# If the destination file could not be deleted, notify the user
				# of this and stop the operation
				self.error_message.emit(
					_("Error saving file"),
					_("Could not replace {}").format(kwargs['destination'])
				)
				reply.deleteLater()
				return
		# Copy the temp file to its destination
		if not kwargs['tmp_file'].copy(kwargs['destination']):
			self.error_message.emit(
				_("Error saving file"),
				_("Could not save file to {}").format(kwargs['destination'])
			)
			reply.deleteLater()
			return

		fcb = kwargs.pop('finished_callback',None)
		if callable(fcb):
			fcb(reply, *args, **kwargs)
		reply.deleteLater()


	def handle_login(self):
		self.get_logged_in_user(self.set_logged_in_user)

	def handle_logout(self):
		self.osf.reset_session()
		self.logged_in_user = {}

	### Other callbacks

	def set_logged_in_user(self, user_data):
		""" Callback function - Locally saves the data of the currently logged_in user """
		self.logged_in_user = json.loads(user_data.readAll().data().decode())
