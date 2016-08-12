# -*- coding: utf-8 -*-

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
import QOpenScienceFramework.connection as osf
# Python warnings
import warnings
# UUID generation
import uuid

# OSF modules
from QOpenScienceFramework import events
from QOpenScienceFramework.widgets import LoginWindow
# Python 2 and 3 compatiblity settings
from QOpenScienceFramework.compat import *

# Easier function decorating
from functools import wraps
# PyQt modules
from qtpy import QtCore, QtNetwork, QtWidgets, QtGui

# Dummy function later to be replaced for translation
_ = lambda s: s

class ConnectionManager(QtNetwork.QNetworkAccessManager):
	"""
	The connection manager does most of the heavy lifting in communicating with the
	OSF. It is responsible for all the HTTP requests and the correct treatment of
	responses from the OSF. """

	# The maximum number of allowed redirects
	MAX_REDIRECTS = 5
	error_message = QtCore.Signal('QString','QString')
	"""PyQt signal to send an error message."""
	warning_message = QtCore.Signal('QString','QString')
	"""PyQt signal to send a warning message."""
	info_message = QtCore.Signal('QString','QString')
	"""PyQt signal to send an info message."""
	success_message = QtCore.Signal('QString','QString')
	"""PyQt signal to send a success message."""

	# Dictionary holding requests in progress, so that they can be repeated if
	# mid-request it is discovered that the OAuth2 token is no longer valid.
	pending_requests = {}

	def __init__(self, *args, **kwargs):
		""" Constructor

		Parameters
		----------
		tokenfile : str (default: 'token.json')
			The path to the file in which the token information should be stored.
		notifier : QtCore.QObject (default: None)
			The object containing pyqt slots / callables to which this object's
			message signals can be connected. The object should contain the following
			slots / functions: info, error, success, warning. Each of these
			should expect two strings. This object is then repsonsible for displaying
			the messages, or passing them on to another object responsible for
			the display. 

			If ``None`` is passed, then a events.Notifier object is
			created which simply displays all messages in QDialog boxes
		"""
		# See if tokenfile and notifier are specified as keyword args
		tokenfile = kwargs.pop("tokenfile", "token.json")
		notifier  = kwargs.pop("notifier", None)

		# Call parent's constructor
		super(ConnectionManager, self).__init__(*args, **kwargs)
		self.tokenfile = tokenfile
		self.dispatcher = events.EventDispatcher()

		# Notifications
		if notifier is None:
			self.notifier = events.Notifier()
		else:
			if not isinstance(notifier, QtCore.QObject):
				raise TypeError('notifier needs to be a class that inherits '
					'from QtCore.QObject')
			if not hasattr(notifier, 'info'):
				raise AttributeError('notifier object is missing a pyqt slot '
					' named info(str, str)')
			if not hasattr(notifier, 'error'):
				raise AttributeError('notifier object is missing a pyqt slot '
					' named error(str, str)')
			if not hasattr(notifier, 'success'):
				raise AttributeError('notifier object is missing a pyqt slot '
					' named success(str, str)')
			if not hasattr(notifier, 'warning'):
				raise AttributeError('notifier object is missing a pyqt slot '
					' named warning(str, str)')
			self.notifier = notifier

		self.error_message.connect(self.notifier.error)
		self.info_message.connect(self.notifier.info)
		self.success_message.connect(self.notifier.success)
		self.warning_message.connect(self.notifier.warning)

		# Init browser in which login page is displayed
		self.browser = LoginWindow()
		self.browser.setWindowTitle(_(u"Log in to OSF"))
		# Make sure browser closes if parent QWidget closes
		if isinstance(self.parent(), QtWidgets.QWidget):
			self.parent().destroyed.connect(self.browser.close)

		# Connect browsers logged in event to that of dispatcher's
		self.browser.logged_in.connect(self.dispatcher.dispatch_login)
		self.logged_in_user = {}

		self.config_mgr = QtNetwork.QNetworkConfigurationManager(self)

		# The icon to show on the progress dialog
		self._progress_icon = None

	### properties
	@property
	def progress_icon(self):
		""" The icon to show on the progress dialog."""
		return self._progress_icon

	@progress_icon.setter
	def progress_icon(self, val):
		if not isinstance(val, QtGui.QIcon) and not val is None:
			raise TypeError('progress_icon should be a QtGui.QIcon or None')
		self._progress_icon = val

	### Private functions
	
	def __logout_succeeded(self, data, *args):
		""" Callback for logout(). 
		Called when logout has succeeded. This function
		dispatches the logout signal to all other connected elements. """
		self.dispatcher.dispatch_logout()

	def __logout_failed(self, data, *args):
		""" Callback for logout(). 
		Called when logout has failed. """
		self.dispatcher.dispatch_login()

	### Login and Logout functions

	def login(self):
		""" Logs in a user. Checks if a token file is stored which can be used to 
		login a user. If not or the token file is invalid, it opens a browser 
		window through which a user can log in. After a successful login, the 
		browser widget fires the 'logged_in' event. """

		# If a valid stored token is found, read that in an dispatch login event
		if self.check_for_stored_token(self.tokenfile):
			self.dispatcher.dispatch_login()
			return
		# Otherwise, do the whole authentication dance
		self.show_login_window()

	def check_for_stored_token(self, tokenfile):
		""" Checks for stored token information. Checks if a token.json file can be
		found at the supplied location and inspects if it is not expired.

		Parameters
		----------
		tokenfile : str
			Path to the token file

		Returns
		-------
		bool
			True if a valid token was found at tokenfile's location, False otherwise
		"""

		logging.info("Looking for token at {}".format(tokenfile))

		if not os.path.isfile(tokenfile):
			return False

		try:
			token = json.load(open(tokenfile))
		except IOError:
			warnings.warn("Token file could not be opened.")
			return False

		# Check if token has not yet expired
		if token["expires_at"] > time.time() :
			# Load the token information in the session object
			osf.session.token = token
			return True
		else:
			osf.session = osf.create_session()
			os.remove(tokenfile)
			logging.info("Token expired; need log-in")
			return False

	def show_login_window(self):
		""" Shows the login page on OSF. """
		auth_url, state = osf.get_authorization_url()

		# Set up browser
		browser_url = get_QUrl(auth_url)

		self.browser.load(browser_url)
		self.browser.show()
		self.browser.raise_()
		self.browser.activateWindow()

	def logout(self):
		""" Logs the current user out from OSF. """
		if osf.is_authorized() and osf.session.access_token:
			self.post(
				osf.logout_url,
				self.__logout_succeeded,
				{'token':osf.session.access_token},
				errorCallback=self.__logout_failed
			)

	### Communication with OSF API

	def buffer_network_request(func):
		""" Decorator function, not to be called directly.
		Checks if network is accessible and buffers the network request so
		that it can be sent again if it fails the first time, for instance due to 
		an invalidated OAuth2 token. In this case the user will be presented with 
		the login screen again. If the same user successfully logs in again, the 
		request will be resent. """

		@wraps(func)
		def func_wrapper(inst, *args, **kwargs):
			if inst.logged_in_user:
				# Create an internal ID for this request
				request_id=uuid.uuid4()
				current_request = lambda: func(inst, *args, **kwargs)
				# Add tuple with current user, and request to be performed
				# to the pending request dictionary
				inst.pending_requests[request_id] = (
					inst.logged_in_user['data']['id'],
					current_request)
				# Add current request id to kwargs of function being called
				kwargs['_request_id'] = request_id
			return func(inst, *args, **kwargs)
		return func_wrapper

	def add_token(self, request):
		"""Adds the OAuth2 token to a HTTP request.

		Parameters
		----------
		request : QtNetwork.QNetworkRequest
			The network request item in whose header to add the OAuth2 token

		Returns
		-------
		bool
			True if token could successfully be added to the request, False if not
		"""
		if osf.is_authorized():
			name = safe_encode("Authorization")
			value = safe_encode("Bearer {}".format(osf.session.access_token))
			request.setRawHeader(name, value)
			return True
		else:
			return False

	### Basic HTTP Functions
	def __check_request_parameters(self, url, callback):
		""" Check if the supplied url is of the correct type and if the callback
		parameter is really a callable

		Parameters
		----------
		url : string or QtCore.QUrl
			The target url/endpoint to perform the request on
		callback : callable
			The callback function

		Returns
		-------
		QtCore.QUrl
			The url to send the request to in QUrl format (does nothing if url \
			was already supplied as a QUrl)

		Raises
		------
		TypeError
			if url is not a QUrl or string, or if callback is not a callable
		"""
		if not isinstance(url, QtCore.QUrl) and not isinstance(url, basestring):
			raise TypeError("url should be a string or QUrl object")
		if not isinstance(url, QtCore.QUrl):
			url = QtCore.QUrl(url)
		if not callable(callback):
			raise TypeError("callback should be a function or callable.")
		return url

	@buffer_network_request
	def get(self, url, callback, *args, **kwargs):
		""" Performs a HTTP GET request. 

		The OAuth2 token is automatically added to the
		header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url/endpoint to perform the GET request on
		callback : callable
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
			the reply object as an argument. This function is also called if the
			operation is aborted by the user him/herself.
		progressDialog : QtWidgets.QProgressDialog (default: None)
			The dialog to send the progress indication to. Will be included in the
			reply object so that it is accessible in the downloadProgress slot, by
			calling self.sender().property('progressDialog')
		abortSignal : QtCore.Signal
			This signal will be attached to the reply objects abort() slot, so that
			the operation can be aborted from outside if necessary.
		*args (optional)
			Any other arguments that you want to have passed to the callback
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback

		Returns
		-------
		QtNetwork.QNetworkReply
			The reply object for the current request. Note that if a 301 or 302
			redirect has occurred, a new reply object has been made for the redirect
			and the one returned here is no longer valid.
		"""

		# First check the correctness of the url and callback parameters
		url = self.__check_request_parameters(url, callback)

		# Create network request
		request = QtNetwork.QNetworkRequest(url)

		# Add OAuth2 token
		if not self.add_token(request):
			warnings.warn(_(u"Token could not be added to the request"))

		# Check if this is a redirect and keep a count to prevent endless
		# redirects. If redirect_count is not set, init it to 0
		kwargs['redirect_count'] = kwargs.get('redirect_count',0)

		reply = super(ConnectionManager, self).get(request)

		# If provided, connect the abort signal to the reply's abort() slot
		abortSignal = kwargs.get('abortSignal', None)
		if not abortSignal is None:
			abortSignal.connect(reply.abort)

		# Check if a QProgressDialog has been passed to which the download status
		# can be reported. If so, add it as a property of the reply object
		progressDialog = kwargs.get('progressDialog', None)
		if isinstance(progressDialog, QtWidgets.QProgressDialog):
			progressDialog.canceled.connect(reply.abort)
			reply.setProperty('progressDialog', progressDialog)

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
			lambda: self.__reply_finished(
				callback, *args, **kwargs
			)
		)
		return reply

	@buffer_network_request
	def post(self, url, callback, data_to_send, *args, **kwargs):
		""" Perform a HTTP POST request. 

		The OAuth2 token is automatically added to the
		header if the request is going to an OSF server. This request is mainly used to send
		small amounts of data to the OSF framework (use PUT for larger files, as this is also
		required by the WaterButler service used by the OSF)

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url/endpoint to perform the POST request on.
		callback : function
			The function to call once the request is finished.
		data_to_send : dict
			The data to send with the POST request. keys will be used as variable names
			and values will be used as the variable values.
		*args (optional)
			Any other arguments that you want to have passed to callable.
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback
		"""
		# First check the correctness of the url and callback parameters
		url = self.__check_request_parameters(url, callback)

		if not type(data_to_send) is dict:
			raise TypeError("The POST data should be passed as a dict")

		request = QtNetwork.QNetworkRequest(url)
		request.setHeader(request.ContentTypeHeader,"application/x-www-form-urlencoded");

		# Add OAuth2 token
		if not self.add_token(request):
			warnings.warn(_(u"Token could not be added to the request"))

		# Sadly, Qt4 and Qt5 show some incompatibility in that QUrl no longer has the
		# addQueryItem function in Qt5. This has moved to a differen QUrlQuery object
		if QtCore.PYQT_VERSION_STR < '5':
			postdata = QtCore.QUrl()
		else:
			postdata = QtCore.QUrlQuery()
		# Add data
		for varname in data_to_send:
			postdata.addQueryItem(varname, data_to_send.get(varname))
		# Convert to QByteArray for transport
		if QtCore.PYQT_VERSION_STR < '5':
			final_postdata = postdata.encodedQuery()
		else:
			final_postdata = safe_encode(postdata.toString(QtCore.QUrl.FullyEncoded))
		# Fire!
		reply = super(ConnectionManager, self).post(request, final_postdata)
		reply.finished.connect(lambda: self.__reply_finished(callback, *args, **kwargs))

	@buffer_network_request
	def put(self, url, callback, *args, **kwargs):
		""" Perform a HTTP PUT request. 

		The OAuth2 token is automatically added to the
		header if the request is going to an OSF server. This method should be used
		to upload larger sets of data such as files.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url/endpoint to perform the PUT request on.
		callback : function
			The function to call once the request is finished.
		data_to_send : QIODevice (default : None)
			The file to upload (QFile or other QIODevice type)
		uploadProgess : callable (defualt: None)
			The slot (callback function) for the downloadProgress signal of the
			reply object. This signal is emitted after a certain amount of bytes
			is received, and can be used for instance to update a download progress
			dialog box. The callback function should have two parameters to which
			the transfered and total bytes can be assigned.
		errorCallback : callable (default: None)
			function to call whenever an error occurs. Should be able to accept
			the reply object as an argument. This function is also called if the
			operation is aborted by the user him/herself.
		progressDialog : QtWidgets.QProgressDialog (default: None)
			The dialog to send the progress indication to. Will be included in the
			reply object so that it is accessible in the downloadProgress slot, by
			calling self.sender().property('progressDialog')
		abortSignal : QtCore.Signal
			This signal will be attached to the reply objects abort() slot, so that
			the operation can be aborted from outside if necessary.
		*args (optional)
			Any other arguments that you want to have passed to the callback
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback
		"""
		# First check the correctness of the url and callback parameters
		url = self.__check_request_parameters(url, callback)
		# Don't use pop() here as it will cause a segmentation fault!
		data_to_send = kwargs.get('data_to_send')

		if not data_to_send is None and not isinstance(data_to_send, QtCore.QIODevice):
			raise TypeError("The data_to_send should be of type QtCore.QIODevice")

		request = QtNetwork.QNetworkRequest(url)
		# request.setHeader(request.ContentTypeHeader,"application/x-www-form-urlencoded");

		# Add OAuth2 token
		if not self.add_token(request):
			warnings.warn(_(u"Token could not be added to the request"))

		reply = super(ConnectionManager, self).put(request, data_to_send)
		reply.finished.connect(lambda: self.__reply_finished(callback, *args, **kwargs))

		# Check if a QProgressDialog has been passed to which the download status
		# can be reported. If so, add it as a property of the reply object
		progressDialog = kwargs.get('progressDialog', None)
		if isinstance(progressDialog, QtWidgets.QProgressDialog):
			progressDialog.canceled.connect(reply.abort)
			reply.setProperty('progressDialog', progressDialog)
		elif not progressDialog is None:
			logging.error("progressDialog is not a QtWidgets.QProgressDialog")

		# If provided, connect the abort signal to the reply's abort() slot
		abortSignal = kwargs.get('abortSignal', None)
		if not abortSignal is None:
			abortSignal.connect(reply.abort)

		# Check if a callback has been specified to which the downloadprogress
		# is to be reported
		ulpCallback = kwargs.get('uploadProgress', None)
		if callable(ulpCallback):
			reply.uploadProgress.connect(ulpCallback)

	@buffer_network_request
	def delete(self, url, callback, *args, **kwargs):
		""" Perform a HTTP DELETE request. 

		The OAuth2 token is automatically added to the
		header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url/endpoint to perform the GET request on
		callback : function
			The function to call once the request is finished successfully.
		errorCallback : function (default: None)
			function to call whenever an error occurs. Should be able to accept
			the reply object as an argument. This function is also called if the
			operation is aborted by the user him/herself.
		abortSignal : QtCore.Signal
			This signal will be attached to the reply objects abort() slot, so that
			the operation can be aborted from outside if necessary.
		*args (optional)
			Any other arguments that you want to have passed to the callback
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback
		"""
		# First check the correctness of the url and callback parameters
		url = self.__check_request_parameters(url, callback)
		request = QtNetwork.QNetworkRequest(url)

		# Add OAuth2 token
		if not self.add_token(request):
			warnings.warn(_(u"Token could not be added to the request"))

		# Check if this is a redirect and keep a count to prevent endless
		# redirects. If redirect_count is not set, init it to 0
		kwargs['redirect_count'] = kwargs.get('redirect_count',0)

		reply = super(ConnectionManager, self).deleteResource(request)

		# If provided, connect the abort signal to the reply's abort() slot
		abortSignal = kwargs.get('abortSignal', None)
		if not abortSignal is None:
			abortSignal.connect(reply.abort)

		reply.finished.connect(
			lambda: self.__reply_finished(
				callback, *args, **kwargs
			)
		)
		return reply

	### Convenience HTTP Functions

	def get_logged_in_user(self, callback, *args, **kwargs):
		"""Get logged in user information.
		Contacts the OSF to request data of the currently logged in user

		Parameters
		----------
		callback : function
			The callback function to which the data should be delivered once the
			request is finished

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong
		"""
		api_call = osf.api_call("logged_in_user")
		return self.get(api_call, callback, *args, **kwargs)

	def get_user_projects(self, callback, *args, **kwargs):
		""" Gets current user's projects. Retrieves a list of projects owned by 
		the currently logged in user from OSF

		Parameters
		----------
		callback : function
			The callback function to which the data should be delivered once the
			request is finished

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong
		"""
		api_call = osf.api_call("projects")
		return self.get(api_call, callback, *args, **kwargs)

	def get_project_repos(self, project_id, callback, *args, **kwargs):
		""" Get repos for the specified project.
		Retrieves a list of repositories from the OSF that belong to the passed
		project id.

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
		"""
		api_call = osf.api_call("project_repos", project_id)
		return self.get(api_call, callback, *args, **kwargs)

	def get_repo_files(self, project_id, repo_name, callback, *args, **kwargs):
		"""Retrieves files contained in a repository.
		Retrieves a list of files from the OSF that belong to the indicated
		repository of the passed project id.

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
		"""
		api_call = osf.api_call("repo_files",project_id, repo_name)
		return self.get(api_call, callback, *args, **kwargs)

	def get_file_info(self, file_id, callback, *args, **kwargs):
		""" Gets information about the specified file.
		
		Parameters
		----------
		file_id : string
			The OSF file identifier (e.g. the node id).
		callback : function
			The callback function to which the data should be delivered once the
			request is finished.

		Returns
		-------
		QtNetwork.QNetworkReply or None if something went wrong.
		"""
		
		api_call = osf.api_call("file_info", file_id)
		return self.get(api_call, callback, *args, **kwargs)

	def download_file(self, url, destination, *args, **kwargs):
		""" Downloads a file by a using HTTP GET request. 
		The OAuth2 token is automatically
		added to the header if the request is going to an OSF server.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url that points to the file to download
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
		progressDialog : dict (default : None)
			A dictionary containing data about the file to be transferred. It
			should have two entries:
			filename: The name of the file
			filesize: the size of the file in bytes
		*args (optional)
			Any other arguments that you want to have passed to the callback
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback
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
		kwargs['download_url'] = url
		# Extra call to get() to make sure OAuth2 token is still valid before download
		# is initiated. If not, this way the request can be repeated after the user
		# reauthenticates
		self.get_logged_in_user(self.__download, *args, **kwargs)

	def upload_file(self, url, source_file, *args, **kwargs):
		""" Uploads a file. 
		The file will be stored at the specified destination on the OSF.

		Parameters
		----------
		url : string / QtCore.QUrl
			The target url that points to endpoint handling the upload
		source_file : string / QtCore.QtFile
			The path to the file which should be uploaded.
		finishedCallback : function (default: None)
			The function to call once the upload is finished.
		uploadProgress : function (default: None)
			The slot (callback function) for the uploadProgress signal of the
			reply object. This signal is emitted after a certain amount of bytes
			is received, and can be used for instance to update a upload progress
			dialog box. The callback function should have two parameters to which
			the transfered and total bytes can be assigned.
		errorCallback : function (default: None)
			function to call whenever an error occurs. Should be able to accept
			the reply object as an argument.
		progressDialog : dict (default : None)
			A dictionary containing data about the file to be transferred. It
			should have two entries:
			filename: The name of the file
			filesize: the size of the file in bytes
		*args (optional)
			Any other arguments that you want to have passed to the callback
		**kwargs (optional)
			Any other keywoard arguments that you want to have passed to the callback
		"""
		# Extra call to get() to make sure OAuth2 token is still valid before download
		# is initiated. If not, this way the request can be repeated after the user
		# reauthenticates
		kwargs['upload_url'] = url
		kwargs['source_file'] = source_file
		self.get_logged_in_user(self.__upload, *args, **kwargs)

	### PyQt Slots

	def __reply_finished(self, callback, *args, **kwargs):
		""" Callback for any HTTP request """
		reply = self.sender()
		request = reply.request()
		# Get the error callback function, if set
		errorCallback = kwargs.get('errorCallback', None)
		# Get the request id, if set (only for authenticated requests, if a user
		# is logged in), so it can be repeated if the user is required to
		# reauthenticate.
		current_request_id = kwargs.pop('_request_id', None)

		# If an error occured, just show a simple QMessageBox for now
		if reply.error() != reply.NoError:
			# User not/no longer authenticated to perform this request
			# Show login window again
			if reply.error() == reply.AuthenticationRequiredError:
				# If access is denied, the user's token must have expired
				# or something like that. Dispatch the logout signal and
				# show the login window again
				self.dispatcher.dispatch_logout()
				self.show_login_window()
			# For all other errors
			else:
				# Don't show error notification if user manually cancelled operation.
				# This is undesirable most of the time, and when it is required, it
				# can be implemented by using the errorCallback function
				if reply.error() != reply.OperationCanceledError:
					self.error_message.emit(
						str(reply.attribute(request.HttpStatusCodeAttribute)),
						reply.errorString()
					)

				# Remove this request from pending requests because it should not
				# be repeated upon reauthentication of the user
				if not current_request_id is None:
					self.pending_requests.pop(current_request_id, None)
				# Close any remaining file handles that were created for upload
				# or download
				self.__close_file_handles(*args, **kwargs)

			# Call error callback, if set
			if callable(errorCallback):
				errorCallback(reply)
			reply.deleteLater()
			return

		# For all other options that follow below, this request can be erased
		# from pending requests.
		if not current_request_id is None:
			self.pending_requests.pop(current_request_id, None)

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
				# Close any remaining file handles that were created for upload
				# or download
				self.__close_file_handles(*args, **kwargs)
				reply.deleteLater()
				return
			# Perform another request with the redirect_url and pass on the callback
			redirect_url = reply.attribute(request.RedirectionTargetAttribute)
			# For now, the redirects only work for GET operations (but to my
			# knowledge, those are the only operations they occur for)
			if reply.operation() == self.GetOperation:
				self.get(redirect_url, callback, *args, **kwargs)
		else:
			# Remove (potentially) internally used kwargs before passing
			# data on to the callback
			kwargs.pop('redirect_count', None)
			kwargs.pop('downloadProgress', None)
			kwargs.pop('uploadProgress', None)
			kwargs.pop('readyRead', None)
			kwargs.pop('errorCallback', None)
			kwargs.pop('abortSignal', None)
			callback(reply, *args, **kwargs)

		# Cleanup, mark the reply object for deletion
		reply.deleteLater()

	def __create_progress_dialog(self, text, filesize):
		""" Creates a progress dialog. Uses manager.progress_icon (if set) to 
		determine which icon to display on the dialog.

		Parameters
		----------
		text : str
			The label to display on the dialog
		filesize : int
			The size of the file being transfered in bytes

		Returns
		-------
		QtWidgets.QProgressDialog
		"""
		progress_dialog = QtWidgets.QProgressDialog()
		progress_dialog.hide()
		progress_dialog.setLabelText(text)
		progress_dialog.setMinimum(0)
		progress_dialog.setMaximum(filesize)
		if self._progress_icon:
			progress_dialog.setWindowIcon(self._progress_icon)
			progress_dialog.setWindowTitle(_(u"Transferring"))
		return progress_dialog

	def __transfer_progress(self, transfered, total):
		""" callback for a reply object. """
		self.sender().property('progressDialog').setValue(transfered)

	def __download(self, reply, download_url, *args, **kwargs):
		""" The real download function, that is a callback for get_logged_in_user()
		in download_file() """
		# Create tempfile
		tmp_file = QtCore.QTemporaryFile()
		tmp_file.open(QtCore.QIODevice.WriteOnly)
		kwargs['tmp_file'] = tmp_file

		progressDialog = kwargs.get('progressDialog', None)
		if isinstance(progressDialog, dict):
			try:
				text = _("Downloading") + " " + progressDialog['filename']
				size = progressDialog['filesize']
			except KeyError as e:
				raise KeyError("progressDialog missing field {}".format(e))
			icon = QtGui.QIcon()
			title = _("Transfer in progress")
			progress_indicator = self.__create_progress_dialog(text, size)
			kwargs['progressDialog'] = progress_indicator
			kwargs['downloadProgress'] = self.__transfer_progress

		# Callback function for when bytes are received
		kwargs['readyRead'] = self.__download_readyRead
		# Download the file with a get request
		self.get(download_url, self.__download_finished, *args, **kwargs)

	def __download_readyRead(self, *args, **kwargs):
		""" callback for a reply object to indicate that data is ready to be
		written to a buffer. """

		reply = self.sender()
		data = reply.readAll()
		if not 'tmp_file' in kwargs or not isinstance(kwargs['tmp_file'], QtCore.QTemporaryFile):
			raise AttributeError('Missing file handle to write to')
		kwargs['tmp_file'].write(data)

	def __download_finished(self, reply, *args, **kwargs):
		""" Callback for a reply object of a GET request, indicating that all
		expected data has been received. """

		progressDialog = kwargs.pop('progressDialog', None)
		if isinstance(progressDialog, QtWidgets.QWidget):
			progressDialog.deleteLater()
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
				return
		# Copy the temp file to its destination
		if not kwargs['tmp_file'].copy(kwargs['destination']):
			self.error_message.emit(
				_("Error saving file"),
				_("Could not save file to {}").format(kwargs['destination'])
			)
			return

		fcb = kwargs.pop('finishedCallback',None)
		if callable(fcb):
			fcb(reply, *args, **kwargs)

	def __upload(self, reply, upload_url, source_file, *args, **kwargs):
		""" Callback for get_logged_in_user() in upload_file(). Does the real
		uploading. """
		# Put checks for the url to be a string or QUrl
		# Check source file
		if isinstance(source_file, basestring):
			# Check if the specified file exists, because a situation is possible in which
			# the user has deleted the file in the meantime in another program.
			# show a message box, but do not raise an exception, because we don't want this
			# to completely crash our program.
			if not os.path.isfile(os.path.abspath(source_file)):
				self.error_message.emit(_("{} is not a valid source file").format(source_file))
				return

			# Open source file for reading
			source_file = QtCore.QFile(source_file)
		elif not isinstance(source_file, QtCore.QIODevice):
			self.error_message.emit(_("{} is not a string or QIODevice instance").format(source_file))
			return

		progressDialog = kwargs.pop('progressDialog', None)
		if isinstance(progressDialog, dict):
			try:
				text = _("Uploading") + " " + os.path.basename(progressDialog['filename'])
				size = progressDialog['filesize']
			except KeyError as e:
				raise KeyError("progressDialog is missing field {}".format(e))
			progress_indicator = self.__create_progress_dialog(text, size)
			kwargs['progressDialog'] = progress_indicator
			kwargs['uploadProgress'] = self.__transfer_progress

		source_file.open(QtCore.QIODevice.ReadOnly)
		self.put(upload_url, self.__upload_finished, data_to_send=source_file,
			*args, **kwargs)

	def __upload_finished(self, reply, *args, **kwargs):
		""" Callback for the reply object of a PUT request, indicating that all
		data has been sent. """
		progressDialog = kwargs.pop('progressDialog', None)
		if isinstance(progressDialog, QtWidgets.QWidget):
			progressDialog.deleteLater()
		if not 'data_to_send' in kwargs or not isinstance(kwargs['data_to_send'],
			QtCore.QIODevice):
			raise AttributeError("No valid open file handle")
		# Close the source file
		kwargs['data_to_send'].close()

		# If another external callback function was provided, call it below
		fcb = kwargs.pop('finishedCallback',None)
		if callable(fcb):
			fcb(reply, *args, **kwargs)

	def __close_file_handles(self, *args, **kwargs):
		""" Closes any open file handles after a failed transfer. Called by
		__reply_finished when a HTTP response code indicating an error has been
		received """
		# When a download is failed, close the file handle stored in tmp_file
		tmp_file = kwargs.pop('tmp_file', None)
		if isinstance(tmp_file, QtCore.QIODevice):
			tmp_file.close()
		# File uploads are stored in data_to_send
		data_to_send = kwargs.pop('data_to_send', None)
		if isinstance(data_to_send, QtCore.QIODevice):
			data_to_send.close()

	### Other callbacks

	def handle_login(self):
		""" Handles the login event received after login. """
		self.get_logged_in_user(self.set_logged_in_user)

	def handle_logout(self):
		""" Handles the logout event received after a logout. """
		self.logged_in_user = {}

	def set_logged_in_user(self, user_data):
		""" Callback function, not to be called directly.

		Locally saves the data of the currently logged_in user """
		self.logged_in_user = json.loads(safe_decode(user_data.readAll().data()))

		# If user had any pending requests from previous login, execute them now
		for (user_id, request) in self.pending_requests.values():
			if user_id == self.logged_in_user['data']['id']:
				request()
		self.pending_requests = {}
