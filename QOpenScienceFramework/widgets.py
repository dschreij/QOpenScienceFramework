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

import os
import re
import sys
import json
import logging
import webbrowser
import warnings
logging.basicConfig(level=logging.INFO)

# QtAwesome icon fonts for spinners
import qtawesome as qta
# OSF connection interface
import QOpenScienceFramework.connection as osf
# Fileinspector for determining filetypes
import fileinspector
# For presenting numbers in human readible formats
import humanize
# For better time functions
import arrow
# Unix style filename matching
import fnmatch
# QT classes
# Required QT classes
from qtpy import QtGui, QtCore, QtWidgets, QtNetwork

import pprint
pp = pprint.PrettyPrinter(indent=2)

# Python 2 and 3 compatiblity settings
from QOpenScienceFramework.compat import *
from QOpenScienceFramework import dirname
osf_logo_path = os.path.join(dirname, 'img/cos-white2.png')
osf_blacklogo_path = os.path.join(dirname, 'img/cos-black.png')

# Dummy function later to be replaced for translation
_ = lambda s: s

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

class UserBadge(QtWidgets.QWidget):
	""" A Widget showing the logged in user """

	# Class variables
	# Login and logout events
	logout_request = QtCore.pyqtSignal()
	login_request = QtCore.pyqtSignal()

	def __init__(self, manager, icon_size=None):
		""" Constructor

		Parameters
		----------
		manager : manger.ConnectionManager
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
		""" Handles a click on the login button """
		if not self.manager.logged_in_user:
			self.login_request.emit()

	def __clicked_logout(self):
		""" Handles a click on the logout button """
		self.user_button.hide()
		self.login_button.show()
		self.login_button.setText(self.logging_out_text)
		QtCore.QCoreApplication.instance().processEvents()
		self.logout_request.emit()

	# Other callback functions

	def handle_login(self):
		""" Callback function for EventDispatcher when a login event is detected """
		self.login_button.setIcon(self.spinner)
		self.login_button.setText(self.logging_in_text)
		# Get logged in user from manager, if something goes wrong, reset the login
		# button status
		self.manager.get_logged_in_user(
			self.__set_badge_contents,
			errorCallback=self.handle_logout
		)

	def handle_logout(self, *args):
		""" Callback function for EventDispatcher when a logout event is detected """
		self.login_button.setIcon(self.osf_icon)
		self.login_button.setText(self.login_text)

	def __set_badge_contents(self, reply):
		""" Sets the user's information in the badge """
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
		""" Sets the photo of the user in the userbadge """
		avatar_data = reply.readAll().data()
		avatar_img = QtGui.QImage()
		success = avatar_img.loadFromData(avatar_data)
		if not success:
			warnings.warn("Could not load user's profile picture")
		pixmap = QtGui.QPixmap.fromImage(avatar_img)
		self.user_button.setIcon(QtGui.QIcon(pixmap))

class OSFExplorer(QtWidgets.QWidget):
	""" An explorer of the current user's OSF account """
	# Size of preview icon in properties pane
	preview_size = QtCore.QSize(150,150)
	button_icon_size = QtCore.QSize(20,20)
	# Formatting of date displays
	timeformat = 'YYYY-MM-DD HH:mm'
	datedisplay = '{} ({})'
	# The maximum size an image may have to be downloaded for preview
	preview_size_limit = 1024**2/2.0
	# Signal that is sent if image preview should be aborted
	abort_preview = QtCore.pyqtSignal()

	def __init__(self, manager, tree_widget=None, locale='en_us'):
		""" Constructor

		Can be passed a reference to an already existing ProjectTree if desired,
		otherwise it creates a new instance of this object.

		Parameters
		----------
		manager : manger.ConnectionManager
			The object taking care of all the communication with the OSF
		tree_widget : ProjectTree (default: None)
			The kind of object, which can be project, folder or file
		locale : string (default: en-us)
			The language in which the time information should be presented.\
			Should consist of lowercase characters only (e.g. nl_nl)
		"""
		# Call parent's constructor
		super(OSFExplorer, self).__init__()

		self.manager = manager

		self.setWindowTitle(_("Project explorer"))
		self.resize(800,500)
		# Set Window icon
		if not os.path.isfile(osf_blacklogo_path):
			raise IOError("OSF logo not found at expected path: {}".format(
				osf_blacklogo_path))
		osf_icon = QtGui.QIcon(osf_blacklogo_path)
		self.setWindowIcon(osf_icon)

		# Set up the title widget (so much code for a simple header with image...)
		self.title_widget = QtWidgets.QWidget(self)
		self.title_widget.setLayout(QtWidgets.QHBoxLayout(self))
		title_logo = QtWidgets.QLabel(self)
		title_logo.setPixmap(osf_icon.pixmap(QtCore.QSize(32,32)))
		title_label = QtWidgets.QLabel("<h1>Open Science Framework</h1>", self)
		self.title_widget.layout().addWidget(title_logo)
		self.title_widget.layout().addWidget(title_label)
		self.title_widget.layout().addStretch(1)
		self.title_widget.setContentsMargins(0,0,0,0)
		self.title_widget.layout().setContentsMargins(0,0,0,0)
		self.title_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
			QtWidgets.QSizePolicy.Fixed)

		## globally accessible items
		self.locale = locale
		# ProjectTree widget. Can be passed as a reference to this object.
		if tree_widget is None:
			# Create a new ProjectTree instance
			self.tree = ProjectTree()
		else:
			# Check if passed reference is a ProjectTree instance
			if type(tree_widget) != ProjectTree:
				raise TypeError("Passed tree_widget should be a 'ProjectTree'\
					instance.")
			else:
				# assign passed reference of ProjectTree to this instance
				self.tree = tree_widget

		self.tree.setSortingEnabled(True)
		self.tree.sortItems(0, QtCore.Qt.AscendingOrder)
		self.tree.contextMenuEvent = self.__show_tree_context_menu

		# File properties overview
		properties_pane = self.__create_properties_pane()

		# The section in which the file icon or the image preview is presented
		preview_area = QtWidgets.QVBoxLayout()
		# Space for image
		self.image_space = QtWidgets.QLabel()
		self.image_space.setAlignment(QtCore.Qt.AlignCenter)
		self.image_space.resizeEvent = self.__resizeImagePreview

		# This holds the image preview in binary format. Everytime the img preview
		# needs to be rescaled, it is done with this variable as the img source
		self.current_img_preview = None

		# The progress bar depicting the download state of the image preview
		self.img_preview_progress_bar = QtWidgets.QProgressBar()
		self.img_preview_progress_bar.setAlignment(QtCore.Qt.AlignCenter)
		self.img_preview_progress_bar.hide()

		preview_area.addWidget(self.image_space)
		preview_area.addWidget(self.img_preview_progress_bar)

		## Create layouts

		# The box layout holding all elements
		self.main_layout = QtWidgets.QVBoxLayout(self)

		# Grid layout for the info consisting of an image space and the
		# properties grid
		info_grid = QtWidgets.QVBoxLayout()
		info_grid.setSpacing(10)
		info_grid.addLayout(preview_area)
		info_grid.addLayout(properties_pane)

		# The widget to hold the infogrid
		self.info_frame = QtWidgets.QWidget()
		self.info_frame.setLayout(info_grid)
		self.info_frame.setVisible(False)

		# Combine tree and info frame with a splitter in the middle
		splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
		splitter.addWidget(self.tree)
		splitter.addWidget(self.info_frame)

		# Create buttons at the bottom
		self.buttonbar = self.__create_buttonbar()

		# Add splitter to extra parent widget to allow overlay

		self.login_required_overlay = QtWidgets.QLabel(
			_(u"Log in to the OSF to use this module"))
		self.login_required_overlay.setStyleSheet(
			"""
			font-size: 20px;
			background: rgba(250, 250, 250, 0.75);
			""")
		self.login_required_overlay.setAlignment(
			QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)

		# Content pane with tree and properties view
		# Also has overlay showing login required message when use is logged
		# out
		content_pane = QtWidgets.QWidget(self)
		content_layout = QtWidgets.QGridLayout()
		content_layout.setContentsMargins(0, 0, 0, 0)
		content_pane.setLayout(content_layout)
		content_layout.addWidget(splitter, 1, 1)
		content_layout.addWidget(self.login_required_overlay, 1, 1)

		# Add to layout
		self.main_layout.addWidget(self.title_widget)
		self.main_layout.addWidget(content_pane)
		self.main_layout.addWidget(self.buttonbar)
		self.main_layout.setContentsMargins(12, 12, 12, 12)
		self.setLayout(self.main_layout)

		# Event connections
		self.tree.currentItemChanged.connect(self.__slot_currentItemChanged)
		self.tree.itemSelectionChanged.connect(self.__slot_itemSelectionChanged)
		self.tree.refreshFinished.connect(self.__tree_refresh_finished)

	### Private functions
	def __resizeImagePreview(self, event):
		""" Resize the image preview (if there is any) after a resize event """
		if not self.current_img_preview is None:
			# Calculate new height, but let the minimum be determined by
			# the y coordinate of preview_size
			new_height = max(event.size().height()-20, self.preview_size.height())
			pm = self.current_img_preview.scaledToHeight(new_height)
			self.image_space.setPixmap(pm)

	def __create_buttonbar(self):
		""" Creates the button bar at the bottom of the explorer """
		# General buttonbar widget
		buttonbar = QtWidgets.QWidget()
		buttonbar_hbox = QtWidgets.QHBoxLayout(buttonbar)
		buttonbar.setLayout(buttonbar_hbox)

		# Refresh button - always visible

		self.refresh_icon = qta.icon('fa.refresh', color='green')
		self.refresh_button = QtWidgets.QPushButton(self.refresh_icon, _('Refresh'))
		self.refresh_icon_spinning = qta.icon(
			'fa.refresh', color='green', animation=qta.Spin(self.refresh_button))
		self.refresh_button.setIconSize(self.button_icon_size)
		self.refresh_button.clicked.connect(self.__clicked_refresh_tree)
		self.refresh_button.setToolTip(_(u"Refresh"))
		self.refresh_button.setDisabled(True)

		# Other buttons, depend on config settings of OSF explorer

		self.new_folder_icon = QtGui.QIcon.fromTheme(
			'folder-new',
			qta.icon('ei.folder-sign')
		)
		self.new_folder_button = QtWidgets.QPushButton(self.new_folder_icon, _('New folder'))
		self.new_folder_button.setIconSize(self.button_icon_size)
		self.new_folder_button.clicked.connect(self.__clicked_new_folder)
		self.new_folder_button.setToolTip(_(u"Create a new folder at the currently"
			" selected location"))
		self.new_folder_button.setDisabled(True)

		self.delete_icon = QtGui.QIcon.fromTheme(
			'edit-delete',
			qta.icon('fa.trash')
		)
		self.delete_button = QtWidgets.QPushButton(self.delete_icon, _('Delete'))
		self.delete_button.setIconSize(self.button_icon_size)
		self.delete_button.clicked.connect(self.__clicked_delete)
		self.delete_button.setToolTip(_(u"Delete the currently selected file or "
			"folder"))
		self.delete_button.setDisabled(True)

		self.download_icon = QtGui.QIcon.fromTheme(
			'go-down',
			qta.icon('fa.cloud-download')
		)
		self.download_button = QtWidgets.QPushButton(self.download_icon,
			_('Download'))
		self.download_button.setIconSize(self.button_icon_size)
		self.download_button.clicked.connect(self._clicked_download_file)
		self.download_button.setToolTip(_(u"Download the currently selected file"))
		self.download_button.setDisabled(True)

		self.upload_icon = QtGui.QIcon.fromTheme(
			'go-up',
			qta.icon('fa.cloud-upload')
		)
		self.upload_button = QtWidgets.QPushButton(self.upload_icon,
			_('Upload'))
		self.upload_button.clicked.connect(self.__clicked_upload_file)
		self.upload_button.setIconSize(self.button_icon_size)
		self.upload_button.setToolTip(_(u"Upload a file to the currently selected"
			" folder"))
		self.upload_button.setDisabled(True)

		# Set up the general button bar layouts
		buttonbar_hbox.addWidget(self.refresh_button)
		buttonbar_hbox.addStretch(1)

		# Add default buttons to default widget
		buttonbar_hbox.addWidget(self.new_folder_button)
		buttonbar_hbox.addWidget(self.delete_button)
		buttonbar_hbox.addWidget(self.download_button)
		buttonbar_hbox.addWidget(self.upload_button)

		# Make sure the button bar is vertically as small as possible.
		buttonbar.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
			QtWidgets.QSizePolicy.Fixed)

		# Store the above buttons (except refresh) into a variable which later
		# can be used to customize button set configurations
		self.buttonsets = {
			'default': []
		}

		self.buttonsets['default'].append(self.new_folder_button)
		self.buttonsets['default'].append(self.delete_button)
		self.buttonsets['default'].append(self.upload_button)
		self.buttonsets['default'].append(self.download_button)

		buttonbar.layout().setContentsMargins(0, 0, 0, 0)

		return buttonbar

	def __create_properties_pane(self):
		""" Creates the panel showing the selected item's properties on the right """
		# Box to show the properties of the selected item
		properties_pane = QtWidgets.QFormLayout()
		properties_pane.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignLeft)
		properties_pane.setLabelAlignment(QtCore.Qt.AlignRight)
		properties_pane.setContentsMargins(15,11,15,40)

		labelStyle = 'font-weight: bold'

		self.common_fields = ['Name','Type']
		self.file_fields = ['Size','Created','Modified','Link']

		self.properties = {}
		for field in self.common_fields + self.file_fields:
			label = QtWidgets.QLabel(_(field))
			label.setStyleSheet(labelStyle)
			if field == "Link":
				# Initialize label with some HTML to trigger the rich text mode
				value = QtWidgets.QLabel('<a></a>')
				value.setOpenExternalLinks(True)
			else:
				value = QElidedLabel('')
				value.setWindowFlags(QtCore.Qt.Dialog)
			self.properties[field] = (label,value)
			properties_pane.addRow(label,value)

		# Make sure the fields specific for files are shown
		for row in self.file_fields:
			for field in self.properties[row]:
				field.hide()
		return properties_pane

	### Public functions
	def create_context_menu(self, item):
		""" Creates a context menu for the currently selected TreeWidgetItem.
		Menu contents differ depending on if the selected item is a file or a
		folder, and if the folder is the root of a repo or a subfolder thereof"""

		data = item.data(0,QtCore.Qt.UserRole)
		# Don't make context menu for a project
		if data['type'] == 'nodes':
			return None

		if data['type'] == 'files':
			kind = data["attributes"]["kind"]

		# Check if the current item is a repository (which is represented as a
		# normal folder)
		parent_data = item.parent().data(0, QtCore.Qt.UserRole)
		if parent_data['type'] == 'nodes':
			item_is_repo = True
		else:
			item_is_repo = False

		menu = QtWidgets.QMenu(self.tree)

		# Actions only allowd on files
		if kind == "file":
			menu.addAction(self.download_icon, _(u"Download file"), 
				self._clicked_download_file)

		# Actions only allowed on folders
		if kind == "folder":
			menu.addAction(self.upload_icon, _(u"Upload file to folder"), 
				self.__clicked_upload_file)
			menu.addAction(self.new_folder_icon, _(u"Create new folder"), 
				self.__clicked_new_folder)
			menu.addAction(self.refresh_icon, _(u"Refresh contents"), 
				self.__clicked_partial_refresh)

		# Only allow deletion of files and subfolders of repos
		if kind == "file" or not item_is_repo:
			menu.addAction(self.delete_icon, _(u"Delete"), self.__clicked_delete)

		return menu

	def add_buttonset(self, title, buttons):
		""" Adds a set of buttons that can be referenced by 'title'. With
		set_buttonset(title) the buttons can be switched to this set.

		Parameters
		----------
		title : str
			The label of the buttonset
		buttons : list
			A list containing QWidgets.QAbstractButton objects that belong to
			this button set

		Raises
		------
		TypeError : if there is no buttonset known by that label or an item in
		the buttons list not an instance of QAbstractButton.
		"""

		# Check if the passed parameters are valid. This function only takes a list
		# (even if the set consists of a single button)
		if not isinstance(buttons, list):
			raise TypeError('"buttons" should be a list with QtWidgets.QAbstractButton'
				' that belong to the set')
		# Check if all items in the list are a QtWidgets.QPushButton
		for bttn in buttons:
			if not isinstance(bttn, QtWidgets.QAbstractButton):
				raise TypeError('All items in the buttons list should be of type'
					' or inherit from QtWidgets.QAbstractButton')
			bttn.setVisible(False)
			self.buttonbar.layout().addWidget(bttn)

		self.buttonsets[title] = buttons

	def show_buttonset(self, title):
		""" Sets the buttonset to show and hides all others

		Parameters
		----------
		title : str
			The label of the buttonset that should be shown

		Raises
		------
		KeyError : if there is no buttonset known by that label
		"""

		if not title in self.buttonsets:
			raise KeyError('Buttonset "{}" could not be found.'.format(title))
		# First hide all items
		for bttnset in self.buttonsets.values():
			for bttn in bttnset:
				bttn.setVisible(False)
		# Then show only the buttons of the specified buttonset
		for bttn in self.buttonsets[title]:
			bttn.setVisible(True)

	def set_file_properties(self, data):
		"""
		Fills the contents of the properties panel for files. Makes sure the
		extra fields concerning files are shown.

		Parameters
		----------
		attributes : dict
			A dictionary containing the information retrieved from the OSF,
			stored at the data/attributes path of the json response
		"""
		# Get required properties
		attributes = data['attributes']

		name = attributes.get("name", "Unspecified")
		filesize = attributes.get("size", "Unspecified")
		created = attributes.get("date_created", "Unspecified")
		modified = attributes.get("date_modified", "Unspecified")

		if check_if_opensesame_file(name):
			filetype = "OpenSesame experiment"
		else:
			# Use fileinspector to determine filetype
			filetype = fileinspector.determine_type(name)
			# If filetype could not be determined, the response is False
			if not filetype is None:
				self.properties["Type"][1].setText(filetype)

				if fileinspector.determine_category(filetype) == "image":
					# Download and display image if it is not too big.
					if not filesize is None and  filesize <= self.preview_size_limit:
						self.img_preview_progress_bar.setValue(0)
						self.img_preview_progress_bar.show()
						self.manager.get(
							data["links"]["download"],
							self.__set_image_preview,
							downloadProgress = self.__prev_dl_progress,
							errorCallback=self.__img_preview_error,
							abortSignal = self.abort_preview
						)

			else:
				filetype = "file"

		# If filesize is None, default to the value 'Unspecified'
		if filesize is None:
			filesize = "Unspecified"
		# If filesize is a number do some reformatting of the data to make it
		# look nicer for us humans
		if filesize != "Unspecified" and isinstance(filesize, int):
			filesize = humanize.naturalsize(filesize)

		# Format created time
		if created != "Unspecified":
			cArrow = arrow.get(created).to('local')
			created = self.datedisplay.format(
				cArrow.format(self.timeformat),
				cArrow.humanize(locale=self.locale)
			)

		# Format modified time
		if modified != "Unspecified":
			mArrow = arrow.get(modified).to('local')
			modified = self.datedisplay.format(
				mArrow.format(self.timeformat),
				mArrow.humanize(locale=self.locale)
			)

		### Set properties in the panel.
		self.properties["Name"][1].setText(name)
		self.properties["Type"][1].setText(filetype)
		self.properties["Size"][1].setText(filesize)
		self.properties["Created"][1].setText(created)
		self.properties["Modified"][1].setText(modified)

		# Make sure the fields specific for files are visible
		for row in self.file_fields:
			for field in self.properties[row]:
				field.show()

		# Get the link to the file on the website of OSF. This is not readily
		# available from the returned API data, but can be parsed from the
		# comments URL, of which it is the [target] filter parameter
		# Sadly, this is URL is not always available for all files, so hide the
		# row if parsing fails.
		try:
			comments_url = data["relationships"]["comments"]["links"]["related"]\
				["href"]
		except KeyError as e:
			warnings.warn('Could not retrieve comments url, because of missing field {}'.format(e))
			self.properties["Link"][0].hide()
			self.properties["Link"][1].hide()
		else:
			# Use regular expression to search for the relevant part of the url
			try:
				target = re.search('filter\[target\]\=\w+', comments_url).group(0)
			except AttributeError:
				# If this didn't work, hide the row altogether
				self.properties["Link"][0].hide()
				self.properties["Link"][1].hide()
			else:
				# Get the ID part of the filter parameter and generate the url
				web_id = target.split("=")[1]
				web_url = u"{}/{}".format(osf.settings['website_url'], web_id)
				a = u"<a href=\"{0}\">{0}</a>".format(web_url)
				# Set the URL in the field
				self.properties["Link"][1].setText(a)
				# Show the row
				self.properties["Link"][0].show()
				self.properties["Link"][1].show()

	def set_folder_properties(self, data):
		"""
		Fills the contents of the properties pane for folders. Make sure the
		fields only concerning files are hidden.

		Parameters
		----------
		attributes : dict
			A dictionary containing the information retrieved from the OSF,
			stored at the data/attributes path of the json response
		"""
		attributes = data['attributes']
		# A node (i.e. a project) has title and category fields
		if "title" in attributes and "category" in attributes:
			self.properties["Name"][1].setText(attributes["title"])
			if attributes["public"]:
				level = "Public"
			else:
				level = "Private"
			self.properties["Type"][1].setText(level + " " + attributes["category"])
		elif "name" in attributes and "kind" in attributes:
			self.properties["Name"][1].setText(attributes["name"])
			self.properties["Type"][1].setText(attributes["kind"])
		else:
			raise osf.OSFInvalidResponse("Invalid structure for folder property"
				" received")

		# Make sure the fields specific for files are shown
		for row in self.file_fields:
			for field in self.properties[row]:
				field.hide()

		# Just to be sure (even though it's useless as these fields are hidden)
		# clear the contents of the fields below
		self.properties["Size"][1].setText('')
		self.properties["Created"][1].setText('')
		self.properties["Modified"][1].setText('')

	def set_config(self, config):
		""" Function that sets the config. Is equal to setting the config variable
		directly by using OSFExplorer.config = <config dict>

		Parameters
		----------
		config : dict
			The dictionary containing new configuration parameters.
		"""

		self.config = config

	@property
	def config(self):
	    return self._config

	@config.setter
	def config(self, value):
		if not isinstance(value, dict):
			raise TypeError('config should be a dict with options')
		self._config = value

		# Get filters
		filt = value.pop('filter', None)
		buttonset = value.pop('buttonset', 'default')

		self.tree.filter = filt
		self.show_buttonset(buttonset)

		if value:
			logging.warning("Unknown options: {}".value.keys())

	### PyQT slots

	def __show_tree_context_menu(self, e):
		""" Shows the context menu when a tree item is right clicked """
		item = self.tree.itemAt(e.pos())
		if item is None:
			return

		context_menu = self.create_context_menu(item)
		if not context_menu is None:
			context_menu.popup(e.globalPos())

	def __slot_currentItemChanged(self, item, col):
		""" Handles the QTreeWidget currentItemChanged event """
		# If selection changed to no item, do nothing
		if item is None:
			return

		# Reset the image preview contents
		self.current_img_preview = None
		self.img_preview_progress_bar.hide()

		# Abort previous preview operation (if any)
		self.abort_preview.emit()

		data = item.data(0, QtCore.Qt.UserRole)
		if data['type'] == 'nodes':
			name = data["attributes"]["title"]
			if data["attributes"]["public"]:
				access = "public "
			else:
				access = "private "
			kind = access + data["attributes"]["category"]
		if data['type'] == 'files':
			name = data["attributes"]["name"]
			kind = data["attributes"]["kind"]

		pm = self.tree.get_icon(kind, name).pixmap(self.preview_size)
		self.image_space.setPixmap(pm)

		if kind  == "file":
			self.set_file_properties(data)
			self.download_button.setDisabled(False)
			self.upload_button.setDisabled(True)
			self.delete_button.setDisabled(False)
			self.new_folder_button.setDisabled(True)
		elif kind == "folder":
			self.set_folder_properties(data)
			self.new_folder_button.setDisabled(False)
			self.download_button.setDisabled(True)
			self.upload_button.setDisabled(False)
			# Check if the parent node is a project
			# If so the current 'folder' must be a storage provider (e.g. dropbox)
			# which should not be allowed to be deleted.
			parent_data = item.parent().data(0, QtCore.Qt.UserRole)
			if parent_data['type'] == 'nodes':
				self.delete_button.setDisabled(True)
			else:
				self.delete_button.setDisabled(False)
		else:
			self.set_folder_properties(data)
			self.new_folder_button.setDisabled(True)
			self.download_button.setDisabled(True)
			self.upload_button.setDisabled(True)
			self.delete_button.setDisabled(True)

	def __slot_itemSelectionChanged(self):
		items_selected = bool(self.tree.selectedItems())
		# If there are selected items, show the properties pane
		if not self.info_frame.isVisible() and items_selected:
			self.info_frame.setVisible(True)
			self.info_frame.resize(300,500)
			return

		if self.info_frame.isVisible() and not items_selected:
			# Reset the image preview contents
			self.current_img_preview = None
			self.info_frame.setVisible(False)
			self.download_button.setDisabled(True)
			self.upload_button.setDisabled(True)
			self.delete_button.setDisabled(True)
			self.refresh_button.setDisabled(True)
			return

	def __clicked_refresh_tree(self):
		""" Refresh the tree contents and animate the refresh button while this
		process is in progress. """

		# Don't do anything if the refresh button is disabled. This probably
		# means a refresh operation is in progress, and activating another one
		# during this is asking for trouble.
		if self.refresh_button.isEnabled() == False:
			return

		self.refresh_button.setDisabled(True)
		self.refresh_button.setIcon(self.refresh_icon_spinning)
		self.tree.refresh_contents()

	def __clicked_partial_refresh(self):
		selected_item = self.tree.currentItem()
		# Don't do anything if the refresh button is disabled. This probably
		# means a refresh operation is in progress, and activating another one
		# during this is asking for trouble.
		if self.refresh_button.isEnabled() == False:
			return
		self.refresh_button.setDisabled(True)
		self.refresh_button.setIcon(self.refresh_icon_spinning)
		self.tree.refresh_children_of_node(selected_item)

	def _clicked_download_file(self):
		""" Action to be performed when download button is clicked. Downloads the
		selected file to the user specified location. """
		selected_item = self.tree.currentItem()
		data = selected_item.data(0, QtCore.Qt.UserRole)
		download_url = data['links']['download']
		filename = data['attributes']['name']

		# See if a previous folder was set, and if not, try to set
		# the user's home folder as a starting folder
		if not hasattr(self, 'last_dl_destination_folder'):
			self.last_dl_destination_folder = safe_decode(
				os.path.expanduser(safe_str("~")),
				enc=sys.getfilesystemencoding())

		destination = QtWidgets.QFileDialog.getSaveFileName(self,
			_("Save file as"),
			os.path.join(self.last_dl_destination_folder, filename),
		)

		# PyQt5 returns a tuple, because it actually performs the function of
		# PyQt4's getSaveFileNameAndFilter() function
		if isinstance(destination, tuple):
			destination = destination[0]

		if destination:
			# Remember this folder for later when this dialog has to be presented again
			self.last_dl_destination_folder = os.path.split(destination)[0]
			# Configure progress dialog (only if filesize is known)
			if data['attributes']['size']:
				progress_dialog_data={
					"filename": filename,
					"filesize": data['attributes']['size']
				}
			else:
				progress_dialog_data = None
			# Download the file
			self.manager.download_file(
				download_url,
				destination,
				progressDialog=progress_dialog_data,
				finishedCallback=self.__download_finished
			)

	def __clicked_delete(self):
		""" Handles a click on the delete button. Deletes the selected file or
		folder. """
		selected_item = self.tree.currentItem()
		data = selected_item.data(0, QtCore.Qt.UserRole)

		reply = QtWidgets.QMessageBox.question(
			self,
			_("Please confirm"),
			_("Are you sure you want to delete '") + data['attributes']['name'] + "'?",
			QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes
		)

		if reply == QtWidgets.QMessageBox.Yes:
			delete_url = data['links']['delete']
			self.manager.delete(delete_url, self.__item_deleted, selected_item)

	def __clicked_upload_file(self):
		""" Handles a click on the upload button. Prepares for upload of a file
		to the currently selected folder. """
		selected_item = self.tree.currentItem()
		data = selected_item.data(0, QtCore.Qt.UserRole)
		upload_url = data['links']['upload']

		# See if a previous folder was set, and if not, try to set
		# the user's home folder as a starting folder
		if not hasattr(self, 'last_open_destination_folder'):
			self.last_open_destination_folder = safe_decode(
				os.path.expanduser(safe_str("~")),
				enc=sys.getfilesystemencoding())

		file_to_upload = QtWidgets.QFileDialog.getOpenFileName(self,
			_("Select file for upload"),
			os.path.join(self.last_open_destination_folder),
		)

		# PyQt5 returns a tuple, because it actually performs the function of
		# PyQt4's getSaveFileNameAndFilter() function
		if isinstance(file_to_upload, tuple):
			file_to_upload = file_to_upload[0]

		if file_to_upload:
			# Get the filename
			folder, filename = os.path.split(file_to_upload)
			# Remember the containing folder for later
			self.last_open_destination_folder = folder
			# ... and the convert to QFile
			file_to_upload = QtCore.QFile(file_to_upload)
			# Check if file is already present and get its index if so
			index_if_present = self.tree.find_item(selected_item, 0, filename)

			# If index_is_present is None, the file is probably new
			if index_if_present is None:
				# add required query parameters
				upload_url += '?kind=file&name={}'.format(filename)
			# If index_is_present is a number, it means the file is present
			# and that file needs to be updated.
			else:
				reply = QtWidgets.QMessageBox.question(
					self,
					_("Please confirm"),
					_("The selected folder already contains this file. Are you "
						"sure you want to overwrite it?"),
					QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes
				)
				if reply == QtWidgets.QMessageBox.No:
					return

				logging.info("File {} exists and will be updated".format(filename))
				old_item = selected_item.child(index_if_present)
				# Get data stored in item
				old_item_data = old_item.data(0,QtCore.Qt.UserRole)
				# Get file specific update utrl
				upload_url = old_item_data['links']['upload']
				upload_url += '?kind=file'
			progress_dialog_data={
				"filename": file_to_upload.fileName(),
				"filesize": file_to_upload.size()
			}

			self.manager.upload_file(
				upload_url,
				file_to_upload,
				progressDialog=progress_dialog_data,
				finishedCallback=self._upload_finished,
				selectedTreeItem=selected_item,
				updateIndex=index_if_present
			)

	def __clicked_new_folder(self):
		""" Creates a new folder in the selected folder on OSF """
		selected_item = self.tree.currentItem()
		data = selected_item.data(0, QtCore.Qt.UserRole)
		# Get new folder link from data
		new_folder_url = data['links']['new_folder']

		new_folder_name, ok = QtWidgets.QInputDialog.getText(self,
			_(u'Create new folder'),
			_(u'Please enter the folder name:')
		)
		new_folder_name = safe_decode(new_folder_name)
		if not ok or not len(new_folder_name):
			return

		# Remove illegal filesystem characters (mainly for Windows)
		new_folder_name = u"".join(i for i in new_folder_name if i not in r'\/:*?"<>|')
		# Check again
		if not len(new_folder_name):
			return

		new_folder_url += "&name={}".format(new_folder_name)
		self.manager.put(
			new_folder_url,
			self._upload_finished,
			selectedTreeItem=selected_item
		)

	def __download_finished(self, reply, *args, **kwargs):
		self.manager.success_message.emit('Download finished','Your download completed successfully')

	def _upload_finished(self, reply, *args, **kwargs):
		""" Callback for reply() object after an upload is finished """
		# See if upload action was triggered by interaction on a tree item
		selectedTreeItem = kwargs.get('selectedTreeItem')
		# The new item data should be returned in the reply
		new_item_data = json.loads(safe_decode(reply.readAll().data()))

		# new_item_data is only reliable for osfstorage for now, so simply
		# refresh the whole tree if data is from another provider.
		if not selectedTreeItem:
			self.__upload_refresh_tree(*args, **kwargs)
		else:
			# See if object is still alive (could be deleted after user has had
			# to reauthenticate)
			try:
				selectedTreeItem.parent()
			except RuntimeError:
				# if not, simple refresh the whole tree
				self.__upload_refresh_tree(*args, **kwargs)
				return

			try:
				provider = new_item_data['data']['attributes']['provider']
			except KeyError as e:
				raise osf.OSFInvalidResponse(
					u'Could not parse provider from OSF response: {}'.format(e))
			# OSF storage is easy. Just take the newly returned path
			if provider == 'osfstorage':
				info_url = osf.api_call('file_info',
					new_item_data['data']['attributes']['path'])
			# All other repo's are a bit more difficult...
			else:
				# Don't even bother for folders and simply refresh the tree.
				# OSF does not provide possibility to get folder information (in
				# contrast to folder contents) for newly created folders in external
				# repositories
				if new_item_data['data']['attributes']['kind'] == 'folder':
					kwargs['entry_node'] = selectedTreeItem
					self.__upload_refresh_tree(*args, **kwargs)
					return

				# If kind is a file, try to add it to the tree incrementally
				# (thus without refreshing the whole tree). At the moment, this
				# only works well for osfstorage...
				try:
					project_id = new_item_data['data']['attributes']['resource']
					temp_id = new_item_data['data']['id']
				except KeyError as e:
					raise osf.OSFInvalidResponse(
						u'Could not parse provider from OSF response: {}'.format(e))

				# Create an url for this file with which the complete information
				# set can be retrieved
				info_url = osf.api_call('repo_files', project_id, temp_id)
				
				# The repo_files api call adds a trailing slash, but this is invalid
				# when requesting information about files. Remove it if present.
				if info_url[-1] == u"/":
					info_url = info_url[:-1]

			# Refresh info for the new file as the returned representation
			# is incomplete

			self.manager.get(
				info_url,
				self.__upload_refresh_item,
				selectedTreeItem,
				*args, **kwargs
			)

	def __upload_refresh_tree(self, *args, **kwargs):
		""" Called by _upload_finished() if the whole tree needs to be
		refreshed """

		# If an entry node is specified, only refresh the children of that node,
		# otherwise, refresh entire tree
		entry_node = kwargs.pop('entry_node', None)
		if entry_node is None:
			self.__clicked_refresh_tree()
		else:
			self.refresh_button.setDisabled(True)
			self.refresh_button.setIcon(self.refresh_icon_spinning)
			self.tree.refresh_children_of_node(entry_node)	

		after_upload_cb = kwargs.pop('afterUploadCallback', None)
		if callable(after_upload_cb):
			after_upload_cb(*args, **kwargs)

	def __upload_refresh_item(self, reply, parent_item, *args, **kwargs):
		""" Called by __upload_finished, if it is possible to add the new item
		at the correct position in the tree, without refreshing the whole tree.
		"""
		item = json.loads(safe_decode(reply.readAll().data()))
		# Remove old item first, before adding new one
		updateIndex = kwargs.get('updateIndex')
		if not updateIndex is None:
			parent_item.takeChild(updateIndex)
		# Add the item as a new item to the tree
		new_item, kind = self.tree.add_item(parent_item, item['data'])
		# Set new item as currently selected item
		self.tree.setCurrentItem(new_item)
		# Store item in kwargs so callback functions can use it
		kwargs['new_item'] = new_item
		# Perform the afterUploadCallback if it has been specified
		after_upload_cb = kwargs.pop('afterUploadCallback', None)
		if callable(after_upload_cb):
			after_upload_cb(*args, **kwargs)

	def __item_deleted(self, reply, item):
		""" Callback for when an item has been successfully deleted from the OSF.
		Removes the item from the tree. """
		# See if object is still alive (could be deleted after user has had
		# to reauthenticate)
		try:
			item.parent().removeChild(item)
		except RuntimeError as e:
			warnings.warn("Deleting item failed: {}".format(e))

	def __tree_refresh_finished(self):
		""" Slot for the event fired when the tree refresh is finished """
		self.refresh_button.setIcon(self.refresh_icon)
		self.refresh_button.setDisabled(False)

	def handle_login(self):
		""" Callback function for EventDispatcher when a login event is detected """
		self.login_required_overlay.setVisible(False)
		self.refresh_button.setDisabled(True)

	def handle_logout(self):
		""" Callback function for EventDispatcher when a logout event is detected """
		self.image_space.setPixmap(QtGui.QPixmap())
		for label,value in self.properties.values():
			value.setText("")
		self.refresh_button.setDisabled(True)
		self.login_required_overlay.setVisible(True)

	def closeEvent(self, event):
		""" Reimplementation of closeEvent. Makes sure the login window also
		closes if the explorer closes. """
		super(OSFExplorer, self).closeEvent(event)
		self.manager.browser.close()

	#--- Other callback functions

	def __set_image_preview(self, img_content):
		""" Callback for set_file_properties(). Sets the preview of an image in
		the properties panel. """
		# Create a pixmap from the just received data
		self.current_img_preview = QtGui.QPixmap()
		self.current_img_preview.loadFromData(img_content.readAll())
		# Scale to preview area hight
		pixmap = self.current_img_preview.scaledToHeight(self.image_space.height())
		# Hide progress bar
		self.img_preview_progress_bar.hide()
		# Show image preview
		self.image_space.setPixmap(pixmap)
		# Reset variable holding preview reply object

	def __prev_dl_progress(self, received, total):
		""" Callback for set_file_properties() """
		# If total is 0, this is probably a redirect to the image location in
		# cloud storage. Do nothing in this case
		if total == 0:
			return

		# Convert to percentage
		progress = 100*received/total
		self.img_preview_progress_bar.setValue(progress)

	def __img_preview_error(self, reply):
		""" Callback for set_file_properties() """
		self.img_preview_progress_bar.hide()

class ProjectTree(QtWidgets.QTreeWidget):
	""" A tree representation of projects and files on the OSF for the current user
	in a treeview widget"""

	# Event fired when refresh of tree is finished
	refreshFinished = QtCore.pyqtSignal()
	# Maximum of items to return per request (e.g. files in a folder). OSF 
	# automatically paginates its results
	ITEMS_PER_PAGE = 50

	def __init__(self, manager, use_theme=None, theme_path='./resources/iconthemes'):
		""" Constructor
		Creates a tree showing the contents of the user's OSF repositories.
		Can be passed a theme to use for the icons, but if this doesn't happen
		it will use the default qtawesome (FontAwesome) icons.

		Parameters
		----------
		manager : manger.ConnectionManager
			The object taking care of all the communication with the OSF
		use_theme : string (default: None)
			The name of the icon theme to use.
		theme_path : The path to the folder at which the icon theme is located
			Relevant only on Windows and OSX as the location of icon themes on
			Linux is standardized.
		"""
		super(ProjectTree, self).__init__()

		self.manager = manager

		# Check for argument specifying that qt_theme should be used to
		# determine icons. Defaults to False.

		if isinstance(use_theme, basestring):
			QtGui.QIcon.setThemeName(os.path.basename(use_theme))
			# Win and OSX don't support native themes
			# so set the theming dir explicitly
			if isinstance(theme_path, basestring) and \
			os.path.exists(os.path.abspath(theme_path)):
				QtGui.QIcon.setThemeSearchPaths(QtGui.QIcon.themeSearchPaths() \
					+ [theme_path])

		# Set up general window
		self.resize(400,500)

		# Set Window icon
		if not os.path.isfile(osf_logo_path):
			logging.error("OSF logo not found at {}".format(osf_logo_path))
		osf_icon = QtGui.QIcon(osf_logo_path)
		self.setWindowIcon(osf_icon)

		# Set column labels
		self.setHeaderLabels(["Name","Kind","Size"])
		self.setColumnWidth(0,300)

		# Event handling
		self.itemExpanded.connect(self.__set_expanded_icon)
		self.itemCollapsed.connect(self.__set_collapsed_icon)
		self.refreshFinished.connect(self.__refresh_finished)

		# Items currently expanded
		self.expanded_items = set()

		# Set icon size for tree items
		self.setIconSize(QtCore.QSize(20,20))

		# Due to the recursive nature of the tree populating function, it is
		# sometimes difficult to keep track of if the populating function is still
		# active. This is a somewhat hacky attempt to artificially keep try to keep
		# track, by adding current requests in this list.
		self.active_requests = []

		# Init filter variable
		self._filter = None

		# Save the previously selected item before a refresh, so this item can
		# be set as the selected item again after the refresh
		self.previously_selected_item = None

		# Flag that indicates if contents are currently refreshed
		self.isRefreshing = False

	### Private functions

	def __set_expanded_icon(self,item):
		data = item.data(0, QtCore.Qt.UserRole)
		if data['type'] == 'files' and data['attributes']['kind'] == 'folder':
			item.setIcon(0,self.get_icon('folder-open',data['attributes']['name']))
		self.expanded_items.add(data['id'])

	def __set_collapsed_icon(self,item):
		data = item.data(0, QtCore.Qt.UserRole)
		if data['type'] == 'files' and data['attributes']['kind'] == 'folder':
			item.setIcon(0,self.get_icon('folder',data['attributes']['name']))
		self.expanded_items.discard(data['id'])

	def __cleanup_reply(self, reply):
		""" Callback for when an error occured while populating the tree, or when
		populate_tree finished successfully. Removes the QNetworkReply
		from the list of active HTTP operations. """
		# Reset active requests after error
		try:
			self.active_requests.remove(reply)
		except ValueError:
			logging.info("Reply not found in active requests")

		if not self.active_requests:
			self.refreshFinished.emit()

	def __refresh_finished(self):
		""" Expands all treewidget items again that were expanded before the
		refresh. """

		# Reapply filter if set
		if self._filter:
			self.filter = self._filter

		iterator = QtWidgets.QTreeWidgetItemIterator(self)
		while(iterator.value()):
			item = iterator.value()
			item_data = item.data(0,QtCore.Qt.UserRole)
			if item_data['id'] in self.expanded_items:
				item.setExpanded(True)
			# Reset selection to item that was selected before refresh
			if self.previously_selected_item:
				if self.previously_selected_item['id'] == item_data['id']:
					self.setCurrentItem(item)
			iterator += 1

		self.isRefreshing = False
	### Properties

	@property
	def filter(self):
	    return self._filter

	@filter.setter
	def filter(self, value):
		""" Only shows tree items that match the specified file extension(s)
		and hides the others

		value : None, str or list
			If None is passed, this clears the filter, making all items present
			in the tree visible again.

			If a string is passed, it will be used as a single file extension
			to compare the items against.

			If a list of file extensions is passed, than items will be shown if
			they match any of the extensions present in the list.
		"""
		# Check if supplied a valid value
		if not isinstance(value, list) and \
		not isinstance(value, basestring) and \
		not value is None:
			raise ValueError('Supplied filter invalid, needs to be list, string'
				' or None')

		# Store the filter for later reference
		self._filter = value

		# Iterate over the items
		iterator = QtWidgets.QTreeWidgetItemIterator(self)
		while(iterator.value()):
			item = iterator.value()
			# Check if item is of type 'file'
			# Filters are only applicable to files
			item_type = item.data(1, QtCore.Qt.DisplayRole)
			if item_type == "file":
				# If filter is None, it means everything should be
				# visible, so set this item to visible and continue.
				if self._filter is None:
					item.setHidden(False)
					iterator += 1
					continue

				# Check if filter extension is contained in filename
				item_data = item.data(0, QtCore.Qt.UserRole)
				filename = item_data['attributes']['name']

				# Assume no match by default
				typematch = False
				# If filter is a single string, just check directly
				if isinstance(self._filter, basestring):
					typematch = fnmatch.fnmatch(filename, self._filter)
				# If filter is a list, compare to each item in it
				if isinstance(self._filter, list):
					for ext in self._filter:
						if fnmatch.fnmatch(filename, ext):
							typematch = True
							break
				# Set item's visibility according to value of typematch
				if typematch:
					item.setHidden(False)
				else:
					item.setHidden(True)
			iterator += 1

	### Public functions

	def set_filter(self, filetypes):
		self.filter = filetypes

	def clear_filter(self):
		self.filter = None

	def find_item(self, item, index, value):
		"""
		Checks if there is already a tree item with the same name as value. This
		function does not recurse over the tree items, it only checks the direct
		descendants of the given item.

		Parameters
		----------
		item : QtWidgets.QTreeWidgetItem
			The tree widget item of which to search the direct descendents.
		index : int
			The column index of the tree widget item.
		value : str
			The value to search for

		Returns
		-------
		int : The index position at which the item is found or None .
		"""
		child_count = item.childCount()
		if not child_count:
			return None

		for i in range(0,child_count):
			child = item.child(i)
			displaytext = child.data(0,QtCore.Qt.DisplayRole)
			if displaytext == value:
				return i
		return None

	def get_icon(self, datatype, name):
		"""
		Retrieves the curren theme icon for a certain object (project, folder)
		or filetype. Uses the file extension to determine the file type.

		Parameters
		----------
		datatype : string
			The kind of object, which can be project, folder or file
		name : string
			The name of the object, which is the project's, folder's or
			file's name

		Returns
		-------
		QtGui.QIcon : The icon for the current file/object type """

		providers = {
			'osfstorage'   : osf_blacklogo_path,
			'github'       : 'web-github',
			'dropbox'      : 'dropbox',
			'googledrive'  : 'web-google-drive',
			'box'          : 'web-microsoft-onedrive',
			'cloudfiles'   : 'web-microsoft-onedrive',
			'dataverse'    : 'web-microsoft-onedrive',
			'figshare'     : 'web-microsoft-onedrive',
			's3'           : 'web-microsoft-onedrive',
		}

		if datatype.lower() in ['public project','private project']:
			# return QtGui.QIcon.fromTheme(
			# 	'gbrainy',
			# 	QtGui.QIcon(osf_logo_path)
			# )
			if datatype.lower() == 'public project':
				return qta.icon('fa.cube', 'fa.globe',
					options=[
						{},
						{'scale_factor': 0.75,
						'offset': (0.2, 0.20),
						'color': 'green'}])
			else:
				return qta.icon('fa.cube')

		if datatype in ['folder','folder-open']:
			# Providers are also seen as folders, so if the current folder
			# matches a provider's name, simply show its icon.
			if name in providers:
				return QtGui.QIcon.fromTheme(
					providers[name],
					QtGui.QIcon(osf_blacklogo_path)
				)
			else:
				return QtGui.QIcon.fromTheme(
					datatype,
					QtGui.QIcon(osf_blacklogo_path)
				)
		elif datatype == 'file':
			# check for OpenSesame extensions first. If this is not an OS file
			# use fileinspector to determine the filetype
			if check_if_opensesame_file(name):
				filetype = 'opera-widget-manager'
			else:
				filetype = fileinspector.determine_type(name,'xdg')

			return QtGui.QIcon.fromTheme(
				filetype,
				QtGui.QIcon.fromTheme(
					'text-x-generic',
					QtGui.QIcon(osf_blacklogo_path)
				)
			)
		return QtGui.QIcon(osf_blacklogo_path)

	def refresh_children_of_node(self, node):
		""" In contrast to refresh_contents, which refreshes the whole tree from
		the root, this function only refreshes the children of the passed node.

		Parameters
		----------
		node : QtWidgets.QTreeWidgetItem
			The tree item of which the children need to be refreshed.
		"""
		if not isinstance(node, QtWidgets.QTreeWidgetItem):
			raise TypeError('node is not a tree widget item')

		# If tree currently is refreshing, do nothing
		if self.isRefreshing == True:
			return
		# Set flag that tree is currently refreshing
		self.isRefreshing = True

		try:
			node_data = node.data(0, QtCore.Qt.UserRole)
		except RuntimeError as e:
			warnings.warn('Partial refresh attempted while tree item was already'
				' deleted')
			self.isRefreshing = False
			return

		try:
			content_url = node_data['relationships']['files']['links'] \
				['related']['href']
		except KeyError as e:
			self.isRefreshing = False
			raise osf.OSFInvalidResponse('Invalid structure of tree item data '
				': {}'.format(e))

		# Delete the current children of the node to make place for the new ones
		node.takeChildren()

		# Retrieve the new listing of children from the OSF
		req = self.manager.get(
			content_url,
			self.populate_tree,
			node,
			errorCallback=self.__cleanup_reply
		)

		# If something went wrong, req should be None
		if req:
			self.active_requests.append(req)

	def refresh_contents(self):
		""" Refreshes all content of the tree """
		# If tree is already refreshing, don't start again, as this will result
		# in a crash
		if self.isRefreshing == True:
			return
		# Set flag that tree is currently refreshing
		self.isRefreshing = True
		# Save current item selection to restore it after refresh
		current_item = self.currentItem()
		if current_item:
			self.previously_selected_item = current_item.data(0,QtCore.Qt.UserRole)
		else:
			self.previously_selected_item = None

		if self.manager.logged_in_user != {}:
			# If manager has the data of the logged in user saved locally, pass it
			# to get_repo_contents directly.
			self.process_repo_contents(self.manager.logged_in_user)
		else:
			# If not, query the osf for the user data, and pass get_repo_contents
			# ass the callback to which the received data should be sent.
			self.manager.get_logged_in_user(
				self.process_repo_contents, errorCallback=self.__cleanup_reply)

	def add_item(self, parent, data):
		if data['type'] == 'nodes':
			name = data["attributes"]["title"]
			if data["attributes"]["public"]:
				access = "public "
			else:
				access = "private "
			kind = data["attributes"]["category"]
			icon_type = access + kind
		if data['type'] == 'files':
			name = data["attributes"]["name"]
			kind = data["attributes"]["kind"]
			icon_type = kind

		values = [name, kind]
		if "size" in data["attributes"] and data["attributes"]["size"]:
			values += [humanize.naturalsize(data["attributes"]["size"])]

		# Create item
		item = QtWidgets.QTreeWidgetItem(parent, values)

		# Set icon
		icon = self.get_icon(icon_type, name)
		item.setIcon(0, icon)

		# Add data
		item.setData(0, QtCore.Qt.UserRole, data)

		return item, kind

	def populate_tree(self, reply, parent=None):
		"""
		Populates the tree with content retrieved from a certain entrypoint,
		specified as an api endpoint of the OSF, such a a project or certain
		folder inside a project. The JSON representation that the api endpoint
		returns is used to build the tree contents. This function is called
		recursively to construct the whole tree of contents on the OSF.

		Parameters
		----------
		reply : QtNetwork.QNetworkReply
			The data from the OSF to create the node in the tree for.
		parent : QtWidgets.QTreeWidgetItem (default: None)
			The parent item to which the generated tree should be attached.
			Is mainly used for the recursiveness that this function implements.
			If not specified the invisibleRootItem() is used as a parent.

		Returns
		-------
		list : The list of tree items that have just been generated """

		osf_response = json.loads(safe_decode(reply.readAll().data()))

		if parent is None:
			parent = self.invisibleRootItem()

		for entry in osf_response["data"]:
			# Add item to the tree. Check if object hasn't been deleted in the
			# meantime
			try:
				item, kind = self.add_item(parent, entry)
			except RuntimeError as e:
				# If a runtime error occured the tree was probably reset or 
				# another event  deleted treeWidgetItems. Not much that can be
				# done here, so do some cleanup and quit
				warnings.warn(e)
				self.__cleanup_reply(reply)
				return

			if kind in ["project","folder"]:
				try:
					next_entrypoint = entry['relationships']['files']\
						['links']['related']['href']
				except AttributeError as e:
					raise osf.OSFInvalidResponse("Invalid api call for getting next"
						"entry point: {}".format(e))
				# Add page size parameter to url to let more than 10 results per page be
				# returned
				next_entrypoint += "?page[size]={}".format(self.ITEMS_PER_PAGE)
				req = self.manager.get(
					next_entrypoint,
					self.populate_tree,
					item,
					errorCallback=self.__cleanup_reply
				)
				# If something went wrong, req should be None
				if req:
					self.active_requests.append(req)

		# If the results are paginated, see if there is another page that needs
		# to be processed
		try:
			next_page_url = osf_response['links']['next']
		except AttributeError as e:
			raise osf.OSFInvalidResponse("Invalid OSF data format for next page of "
				"results. Missing attribute: {}".format(e))

		if not next_page_url is None:
			req = self.manager.get(
				next_page_url,
				self.populate_tree,
				parent,
				errorCallback=self.__cleanup_reply
			)
			# If something went wrong, req should be None
			if req:
				self.active_requests.append(req)

		# Remove current reply from list of active requests (assuming it finished)
		self.__cleanup_reply(reply)

	def process_repo_contents(self, logged_in_user):
		""" Processes contents for the logged in user. Starts by listing
		the projects and then recurses through all their repositories, folders and files. """
		# If this function is called as a callback, the supplied data will be a
		# QByteArray. Convert to a dictionary for easier usage
		if isinstance(logged_in_user, QtNetwork.QNetworkReply):
			logged_in_user = json.loads(safe_decode(logged_in_user.readAll().data()))

		# Get url to user projects. Use that as entry point to populate the project tree
		try:
			user_nodes_api_call = logged_in_user['data']['relationships']['nodes']\
			['links']['related']['href']
		except AttributeError as e:
			raise osf.OSFInvalidResponse(
				"The structure of the retrieved data seems invalid: {}".format(e)
			)
		# Clear the tree to be sure
		self.clear()
		# Add the max items to return per request to the api url
		user_nodes_api_call += "?page[size]={}".format(self.ITEMS_PER_PAGE)

		# Start populating the tree
		req = self.manager.get(
			user_nodes_api_call,
			self.populate_tree,
			errorCallback=self.__cleanup_reply,
		)
		# If something went wrong, req should be None
		if req:
			self.active_requests.append(req)

	# Event handling functions required by EventDispatcher

	def handle_login(self):
		""" Callback function for EventDispatcher when a login event is detected """
		self.active_requests = []
		self.refresh_contents()

	def handle_logout(self):
		""" Callback function for EventDispatcher when a logout event is detected """
		self.active_requests = []
		self.previously_selected_item = None
		self.clear()
