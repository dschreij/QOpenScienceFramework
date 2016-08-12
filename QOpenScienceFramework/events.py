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

#OSF modules
import QOpenScienceFramework.connection as osf

# PyQt modules
from qtpy import QtCore, QtWidgets

class EventDispatcher(QtCore.QObject):
	""" This class fires events to connected classes, which are henceforth
	referenced to as 'listeners'.
	Basically EventDispatcher's purpose is to propagate login and logout events
	to the QWidget subclasses that require authorization at the OSF to function
	correctly, but of course this can be extended with other events that are relevant
	for all listeners.

	The only requirement for listener classes is that they implement a handling
	function for each event that should be named "handle_<event_name>". For example, to catch
	a login event, a listener should have the function handle_login."""

	# List of possible events this dispatcher can emit
	logged_in = QtCore.Signal()
	""" PyQt Signal emitted when a user just logged in. """
	logged_out = QtCore.Signal()
	""" PyQt Signal emitted when a user just logged out. """

	def __init__(self, *args, **kwargs):
		""" Constructor """
		super(EventDispatcher, self).__init__(*args, **kwargs)

	def add_listeners(self, obj_list):
		""" Add one or more object(s) to the list of listeners.

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
		""" Add a new object to listen for the events.

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
		""" Convenience function to dispatch the login event. """
		self.logged_in.emit()

	def dispatch_logout(self):
		""" Convenience function to dispatch the logout event. """
		self.logged_out.emit()

class TokenFileListener(object):
	""" This listener stores the OAuth2 token after login and destroys it after
	logout."""
	def __init__(self,tokenfile):
		""" Constructor """
		super(TokenFileListener,self).__init__()
		self.tokenfile = tokenfile

	def handle_login(self):
		""" Handles the login event. 

		Stores the OAuth2 token in a file.
		"""
		if osf.session.token:
			tokenstr = json.dumps(osf.session.token)
			with open(self.tokenfile,'w') as f:
				f.write(tokenstr)
		else:
			logging.error("Error, could not find authentication token")

	def handle_logout(self):
		""" Handles the logout event. 

		Deletes the file containing the OAuth2 token.
		"""
		if os.path.isfile(self.tokenfile):
			try:
				os.remove(self.tokenfile)
			except Exception as e:
				logging.warning("WARNING: {}".format(e.message))

class Notifier(QtCore.QObject):
	""" This object receives error or info messages and displays them in a
	QMessageBox notification box. It works with Qts signal slot architecture,
	as in all functions are slots to which Qt signals should be connected."""

	def __init__(self):
		""" Constructor """
		super(Notifier,self).__init__()

	@QtCore.Slot('QString', 'QString')
	def error(self, title, message):
		""" Show an error message in a 'critical' QMessageBox.

		Parameters
		----------
		title : str
			The title of the box
		message : str
			The message to display
		"""
		QtWidgets.QMessageBox.critical(None,
			title,
			message
		)

	@QtCore.Slot('QString', 'QString')
	def warning(self, title, message):
		""" Show a warning message in a 'warning' QMessageBox.

		Parameters
		----------
		title : str
			The title of the box
		message : str
			The message to display
		"""
		QtWidgets.QMessageBox.warning(None,
			title,
			message
		)

	@QtCore.Slot('QString', 'QString')
	def info(self, title, message):
		""" Show an info message in an 'information' QMessageBox.

		Parameters
		----------
		title : str
			The title of the box
		message : str
			The message to display
		"""
		QtWidgets.QMessageBox.information(None,
			title,
			message
		)

	@QtCore.Slot('QString', 'QString')
	def success(self, title, message):
		""" Show a success message in a 'success' QMessageBox.

		Parameters
		----------
		title : str
			The title of the box
		message : str
			The message to display
		"""
		QtWidgets.QMessageBox.information(None,
			title,
			message
		)







