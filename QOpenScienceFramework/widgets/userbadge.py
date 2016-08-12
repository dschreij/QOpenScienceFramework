# -*- coding: utf-8 -*-

# Python3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import json
import logging
import webbrowser
import warnings
logging.basicConfig(level=logging.INFO)

# QtAwesome icon fonts for spinners
import qtawesome as qta
# OSF connection interface
import QOpenScienceFramework.connection as osf
# QT classes
# Required QT classes
from qtpy import QtGui, QtCore, QtWidgets

# Python 2 and 3 compatiblity settings
from QOpenScienceFramework.compat import *
from QOpenScienceFramework import dirname
osf_logo_path = os.path.join(dirname, 'img/cos-white2.png')
osf_blacklogo_path = os.path.join(dirname, 'img/cos-black.png')

# Dummy function later to be replaced for translation
_ = lambda s: s

class UserBadge(QtWidgets.QWidget):
	""" A Widget showing the logged in user """

	# Class variables
	# Login and logout events
	logout_request = QtCore.Signal()
	""" PyQt signal to send a logout request. """
	login_request = QtCore.Signal()
	""" PyQt signal to send a login request. """

	def __init__(self, manager, icon_size=None):
		""" Constructor

		Parameters
		----------
		manager : manager.ConnectionManager
			The object taking care of all the communication with the OSF
		iconsize : QtCore.QSize (default: None)
			The size of the icon to use for the osf logo and user photo, if not
			passed a size of 40x40 is used.
		"""
		super(UserBadge, self).__init__()

		# button texts
		self.login_text = _("Log in")
		self.logout_text = _("Log out")
		self.logging_in_text = _("Logging in")
		self.logging_out_text = _("Logging out")

		self.manager = manager
		if isinstance(icon_size, QtCore.QSize):
			# Size of avatar and osf logo display image
			self.icon_size = icon_size
		else:
			self.icon_size = QtCore.QSize(40,40)

		# Set up general window
		# self.resize(200,40)
		self.setWindowTitle(_("User badge"))
		# Set Window icon

		if not os.path.isfile(osf_logo_path):
			print("ERROR: OSF logo not found at {}".format(osf_logo_path))

		self.osf_logo_pixmap = QtGui.QPixmap(osf_logo_path).scaled(self.icon_size)
		self.osf_icon = QtGui.QIcon(osf_logo_path)
		self.setWindowIcon(self.osf_icon)

		# Login button
		self.login_button = QtWidgets.QPushButton(self)
		self.login_button.clicked.connect(self.__clicked_login)
		self.login_button.setIconSize(self.icon_size)
		self.login_button.setFlat(True)

		self.user_button = QtWidgets.QPushButton(self)
		self.user_button.setIconSize(self.icon_size)
		self.logged_in_menu = QtWidgets.QMenu(self.login_button)
		visit_osf_icon = QtGui.QIcon.fromTheme('web-browser', qta.icon('fa.globe'))
		self.logged_in_menu.addAction(
			visit_osf_icon, _(u"Visit osf.io"), self.__open_osf_website)
		logout_icon = QtGui.QIcon.fromTheme('system-log-out', 
			qta.icon('fa.sign-out'))
		self.logged_in_menu.addAction(logout_icon, _(u"Log out"), 
			self.__clicked_logout)
		self.user_button.setMenu(self.logged_in_menu)
		self.user_button.hide()
		self.user_button.setFlat(True)

		# Spinner icon
		self.spinner = qta.icon('fa.refresh', color='green',
					 animation=qta.Spin(self.login_button))

		# Init user badge as logged out
		self.handle_logout()

		# Set up layout
		layout = QtWidgets.QGridLayout(self)
		layout.addWidget(self.login_button, 1, 1)
		layout.addWidget(self.user_button, 1, 1)

		self.login_button.setContentsMargins(0, 0, 0, 0)
		self.user_button.setContentsMargins(0, 0, 0, 0)
		self.layout().setContentsMargins(0, 0, 0, 0)
		self.layout().setSpacing(0)

	def current_user(self):
		""" Checks the current status of the user.

		Returns
		-------
		dict : contains the information of the logged in user, or is empty if no
		user is currently logged in.
		"""
		return self.manager.logged_in_user

	# PyQt slots
	def __open_osf_website(self):
		""" Opens the OSF website in the OS default browser """
		webbrowser.open(osf.website_url)

	def __clicked_login(self):
		""" Handles a click on the login button. """
		if not self.manager.logged_in_user:
			self.login_request.emit()

	def __clicked_logout(self):
		""" Handles a click on the logout button. """
		self.user_button.hide()
		self.login_button.show()
		self.login_button.setText(self.logging_out_text)
		QtCore.QCoreApplication.instance().processEvents()
		self.logout_request.emit()

	# Other callback functions

	def handle_login(self):
		""" Callback function for EventDispatcher when a login event is detected. """
		self.login_button.setIcon(self.spinner)
		self.login_button.setText(self.logging_in_text)
		# Get logged in user from manager, if something goes wrong, reset the login
		# button status
		self.manager.get_logged_in_user(
			self.__set_badge_contents,
			errorCallback=self.handle_logout
		)

	def handle_logout(self, *args):
		""" Callback function for EventDispatcher when a logout event is detected. """
		self.login_button.setIcon(self.osf_icon)
		self.login_button.setText(self.login_text)

	def __set_badge_contents(self, reply):
		""" Sets the user's information in the badge. """
		# Convert bytes to string and load the json data
		user = json.loads(safe_decode(reply.readAll().data()))

		# Get user's name
		try:
			full_name = user["data"]["attributes"]["full_name"]
			# Download avatar image from the specified url
			avatar_url = user["data"]["links"]["profile_image"]
		except KeyError as e:
			raise osf.OSFInvalidResponse("Invalid user data format: {}".format(e))
		self.user_button.setText(full_name)
		self.login_button.hide()
		self.user_button.show()
		# Load the user image in the photo area
		self.manager.get(avatar_url, self.__set_user_photo)

	def __set_user_photo(self, reply):
		""" Sets the photo of the user in the userbadge. """
		avatar_data = reply.readAll().data()
		avatar_img = QtGui.QImage()
		success = avatar_img.loadFromData(avatar_data)
		if not success:
			warnings.warn("Could not load user's profile picture")
		pixmap = QtGui.QPixmap.fromImage(avatar_img)
		self.user_button.setIcon(QtGui.QIcon(pixmap))