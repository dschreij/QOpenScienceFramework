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
import platform
import json
import logging
logging.basicConfig(level=logging.INFO)

# QT classes
# Required QT classes
import qtpy
qtpy.setup_apiv2()
from qtpy import QtGui, QtCore, QtWebKit, QtWidgets
# QtAwesome icon fonts for spinners
import qtawesome as qta
# OSF connection interface
import openscienceframework.connection as osf
# For performing HTTP requests
import requests
# Fileinspector for determining filetypes
import fileinspector
# For presenting numbers in human readible formats
import humanize
# For better time functions
import arrow

osf_logo_path = os.path.abspath('resources/img/cos-white2.png')

def check_for_opensesame_file(filename):
	""" Checks if the passed file is an OpenSesame file, based on its extension.

	Parameters
	----------
	filename : string
		The filename to check

	Returns
	-------
	boolean :
		True if filename is an OpenSesame file, False if not
	"""
	ext = os.path.splitext(filename)[1]
	if ext in ['.osexp','.opensesame'] or \
		(ext == '.gz' and 'opensesame.tar.gz' in filename):
		return True
	return False

class LoginWindow(QtWebKit.QWebView):
	""" A Login window for the OSF """
	# Login event is emitted after successfull login

	# Event fired when user successfully logged in
	logged_in = QtCore.pyqtSignal()

	def __init__(self):
		""" Constructor """
		super(LoginWindow, self).__init__()

		# Create Network Access Manager to listen to all outgoing
		# HTTP requests. Necessary to work around the WebKit 'bug' which
		# causes it drop url fragments, and thus the access_token that the
		# OSF Oauth system returns
		self.nam = self.page().networkAccessManager()

		# Connect event that is fired after an URL is changed
		# (does not fire on 301 redirects, hence the requirement of the NAM)
		self.urlChanged.connect(self.check_URL)

		# Connect event that is fired if a HTTP request is completed.
		self.nam.finished.connect(self.checkResponse)

	def checkResponse(self,reply):
		"""Callback function for NetworkRequestManager.finished event

		Parameters
		----------
		reply : QtNetwork.QNetworkReply
			The HTTPResponse object provided by NetworkRequestManager
		"""
		request = reply.request()
		# Get the HTTP statuscode for this response
		statuscode = reply.attribute(request.HttpStatusCodeAttribute)
		# The accesstoken is given with a 302 statuscode to redirect

		# Stop if statuscode is not 302
		if statuscode != 302:
			return

		redirectUrl = reply.attribute(request.RedirectionTargetAttribute)
		if not redirectUrl.hasFragment():
			return

		r_url = redirectUrl.toString()
		if osf.redirect_uri in r_url:
			logging.info("Token URL: {}".format(r_url))
			self.token = osf.parse_token_from_url(r_url)
			if self.token:
				self.logged_in.emit()
				self.close()

	def check_URL(self, url):
		""" Callback function for urlChanged event.

		Parameters
		----------
		command : url
			New url, provided by the urlChanged event

		"""
		new_url = url.toString()

		if not osf.base_url in new_url and not osf.redirect_uri in new_url:
			logging.warning("URL CHANGED: Unexpected url: {}".format(url))

class UserBadge(QtWidgets.QWidget):
	""" A Widget showing the logged in user """

	# Class variables

	# Size of avatar and osf logo display image
	image_size = QtCore.QSize(50,50)
	# Login and logout events
	logout_request = QtCore.pyqtSignal()
	login_request = QtCore.pyqtSignal()
	# button texts
	login_text = "Log in to OSF"
	logout_text = "Log out"

	def __init__(self, manager):
		""" Constructor """
		super(UserBadge, self).__init__()

		self.manager = manager

		# Set up general window
		self.resize(200,40)
		self.setWindowTitle("User badge")
		# Set Window icon

		if not os.path.isfile(osf_logo_path):
			print("ERROR: OSF logo not found at {}".format(osf_logo_path))

		self.osf_logo_pixmap = QtGui.QPixmap(osf_logo_path).scaled(self.image_size)

		osf_icon = QtGui.QIcon(osf_logo_path)
		self.setWindowIcon(osf_icon)

		## Set up labels
		# User's name
		self.user_name = QtWidgets.QLabel()
		# User's avatar
		self.avatar = QtWidgets.QLabel()

		# Login button
		self.statusbutton = QtWidgets.QPushButton(self)
		self.statusbutton.clicked.connect(self.__handle_click)

		# Spinner icon
		self.spinner = qta.icon('fa.refresh', color='green',
                     animation=qta.Spin(self.statusbutton))

		# Init user badge as logged out
		self.handle_logout()

		# Set up layout
		grid = QtWidgets.QGridLayout()
		grid.setSpacing(5)
		grid.addWidget(self.avatar,1,0)

		login_grid = QtWidgets.QGridLayout()
		login_grid.setSpacing(5)
		login_grid.addWidget(self.user_name,1,1)
		login_grid.addWidget(self.statusbutton,2,1)

		grid.addLayout(login_grid,1,1)
		self.setLayout(grid)

	def current_user(self):
		""" Checks the current status of the user."""
		return self.manager.logged_in_user

	# PyQt slots
	def __handle_click(self):
		button = self.sender()
		logging.info("Button {} clicked".format(button.text()))
		if button.text() == self.login_text:
			self.login_request.emit()
		elif button.text() == self.logout_text:
			button.setText("Logging out...")
			QtCore.QCoreApplication.instance().processEvents()
			self.logout_request.emit()

	def handle_login(self):
		""" Callback function for EventDispatcher when a login event is detected """
		self.statusbutton.setIcon(self.spinner)
		self.statusbutton.setText("Logging in")
		self.manager.get_logged_in_user(self.__set_badge_contents)

	def handle_logout(self):
		""" Callback function for EventDispatcher when a logout event is detected """
		self.user = None
		self.user_name.setText("")
		self.avatar.setPixmap(self.osf_logo_pixmap)
		self.statusbutton.setText(self.login_text)

	# Other callback functions

	def __set_badge_contents(self, data):
		# Convert bytes to string and load the json data
		user = json.loads(data.data().decode())
		# Get user's name
		full_name = user["data"]["attributes"]["full_name"]
		# Download avatar image from the specified url
		avatar_url = user["data"]["links"]["profile_image"]
		avatar_img = requests.get(avatar_url).content
		pixmap = QtGui.QPixmap()
		pixmap.loadFromData(avatar_img)
		pixmap = pixmap.scaled(self.image_size)

		# Update sub-widgets
		self.user_name.setText(full_name)
		self.avatar.setPixmap(pixmap)
		self.statusbutton.setText(self.logout_text)
		self.statusbutton.setIcon(QtGui.QIcon())


class OSFExplorer(QtWidgets.QWidget):
	""" An explorer of the current user's OSF account """
	# Size of preview icon in properties pane
	preview_size = QtCore.QSize(150,150)
	# Formatting of date displays
	timeformat = 'YYYY-MM-DD HH:mm'
	datedisplay = '{}\n({})'
	# The maximum size an image may have to be downloaded for preview
	image_size_limit = 1024**2/2.0

	def __init__(self, manager, tree_widget=None, locale='en_us'):
		""" Constructor

		Can be passed a reference to an already existing ProjectTree if desired,
		otherwise it creates a new instance of this object.

		Parameters
		----------
		tree_widget : ProjectTree (default: None)
			The kind of object, which can be project, folder or file
		locale : string (default: en-us)
			The language in which the time information should be presented.\
			Should consist of lowercase characters only (e.g. nl_nl)
		"""
		# Call parent's constructor
		super(OSFExplorer, self).__init__()

		self.manager = manager

		self.setWindowTitle("Project explorer")
		self.resize(800,500)
		# Set Window icon
		if not os.path.isfile(osf_logo_path):
			print("ERROR: OSF logo not found at {}".format(osf_logo_path))
		osf_icon = QtGui.QIcon(osf_logo_path)
		self.setWindowIcon(osf_icon)

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

		# File properties overview
		properties_pane = self.__create_properties_pane()
		self.image_space = QtWidgets.QLabel()
		self.image_space.setAlignment(QtCore.Qt.AlignCenter)
		self.image_space.resizeEvent = self.__resizeImagePreview
		self.current_img_preview = None

		# Spinner image
		self.spinner = QtWidgets.QLabel()
		self.spinner.setAlignment(QtCore.Qt.AlignCenter)
		self.spinner_icon = qta.icon(
			'fa.spinner',
			color='green',
			animation=qta.Spin(self.spinner)
		)
		spm = self.spinner_icon.pixmap(self.preview_size)
		self.spinner.setPixmap(spm)
		self.spinner.hide()

		# Create layouts
		hbox = QtWidgets.QHBoxLayout(self)

		# Grid layout for the info consisting of an image space and the
		# properties grid
		info_grid = QtWidgets.QGridLayout()
		info_grid.setSpacing(10)
		info_grid.addWidget(self.image_space,1,1)
		info_grid.addWidget(self.spinner,1,1)
		info_grid.addLayout(properties_pane,2,1)

		# The widget to hold the infogrid
		self.info_frame = QtWidgets.QWidget()
		self.info_frame.setLayout(info_grid)
		self.info_frame.setVisible(False)

		splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
		splitter.addWidget(self.tree)
		splitter.addWidget(self.info_frame)

		hbox.addWidget(splitter)
		self.setLayout(hbox)

		# Event connections
		self.tree.itemClicked.connect(self.__item_clicked)
		self.tree.itemSelectionChanged.connect(self.__selection_changed)

	def __resizeImagePreview(self, event):
		""" Resize the image preview (if there is any) after a resize event """
		if not self.current_img_preview is None:
			# Calculate new height, but let the minimum be determined by
			# the y coordinate of preview_size
			new_height = max(event.size().height()-20, self.preview_size.height())
			pm = self.current_img_preview.scaledToHeight(new_height)
			self.image_space.setPixmap(pm)

	### Private functions

	def __create_properties_pane(self):
		# Box to show the properties of the selected item
		properties_pane = QtWidgets.QFormLayout()
		properties_pane.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignLeft)
		properties_pane.setLabelAlignment(QtCore.Qt.AlignRight)
		properties_pane.setContentsMargins(15,11,15,40)

		labelStyle = 'font-weight: bold'

		self.common_fields = ['Name','Type']
		self.file_fields = ['Size','Last touched','Created','Modified']

		self.properties = {}
		for field in self.common_fields + self.file_fields:
			label = QtWidgets.QLabel(field)
			label.setStyleSheet(labelStyle)
			value = QtWidgets.QLabel('')
			self.properties[field] = (label,value)
			properties_pane.addRow(label,value)

		# Make sure the fields specific for files are shown
		for row in self.file_fields:
			for field in self.properties[row]:
				field.hide()

		return properties_pane

	### Public functions

	def set_file_properties(self, data):
		"""
		Fills the contents of the properties pane for files. Makes sure the
		extra fields concerning files are shown.

		Parameters
		----------
		attributes : dict
			A dictionary containing the information retrieved from the OSF,
			stored at the data/attributes path of the json response
		"""
		# Get required properties
		attributes = data['attributes']
		try:
			name = attributes["name"]
			filesize = attributes["size"]
			last_touched = attributes["last_touched"]
			created = attributes["date_created"]
			modified = attributes["date_modified"]
		except AttributeError as e:
			raise osf.OSFInvalidResponse("Error parsing parse OSF response: {}".format(e))

		if check_for_opensesame_file(name):
			filetype = "OpenSesame experiment"
		else:
			# Use fileinspector to determine filetype
			filetype = fileinspector.determine_type(name)
			# If filetype could not be determined, the response is False
			if filetype != False:
				self.properties["Type"][1].setText(filetype)

				if fileinspector.determine_category(filetype) == "image":
					# Download and display image if it is not too big.
					if filesize <= self.image_size_limit:
						self.manager.get(
							data["links"]["download"],
							self.set_image_preview)
						self.spinner.show()
			else:
				filetype = "file"

		### Do some reformatting of the data to make it look nicer for us humans
		filesize = humanize.naturalsize(filesize)

		# Last touched will be None if the file has never been 'touched'
		# Change this to "Never"
		if not last_touched is None:
			# Format last touched time
			ltArrow = arrow.get(last_touched)
			last_touched = self.datedisplay.format(
				ltArrow.format(self.timeformat),
				ltArrow.humanize(locale=self.locale)
			)
		else:
			last_touched = "Never"

		# Format created time
		cArrow = arrow.get(created)
		created = self.datedisplay.format(
			cArrow.format(self.timeformat),
			cArrow.humanize(locale=self.locale)
		)

		# Format modified time
		mArrow = arrow.get(modified)
		modified = self.datedisplay.format(
			mArrow.format(self.timeformat),
			mArrow.humanize(locale=self.locale)
		)

		### Set properties in the panel.
		self.properties["Name"][1].setText(name)
		self.properties["Type"][1].setText(filetype)
		self.properties["Size"][1].setText(filesize)
		self.properties["Last touched"][1].setText(last_touched)
		self.properties["Created"][1].setText(created)
		self.properties["Modified"][1].setText(modified)

		# Make sure the fields specific for files are visible
		for row in self.file_fields:
			for field in self.properties[row]:
				field.show()

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
			self.properties["Type"][1].setText(attributes["category"])
		elif "name" in attributes and "kind" in attributes:
			self.properties["Name"][1].setText(attributes["name"])
			self.properties["Type"][1].setText(attributes["kind"])
		else:
			raise osf.OSFInvalidResponse("Invalid structure for folder propertie received")

		# Make sure the fields specific for files are shown
		for row in self.file_fields:
			for field in self.properties[row]:
				field.hide()

		# Just to be sure (even though it's useless as these fields are hidden)
		# clear the contents of the fields below
		self.properties["Size"][1].setText('')
		self.properties["Last touched"][1].setText('')
		self.properties["Created"][1].setText('')
		self.properties["Modified"][1].setText('')


	### PyQT slots

	def __item_clicked(self,item,col):
		""" Handles the QTreeWidget itemClicked event """
		# Reset the image preview contents
		self.current_img_preview = None

		data = item.data
		if data['type'] == 'nodes':
			name = data["attributes"]["title"]
			kind = data["attributes"]["category"]
		if data['type'] == 'files':
			name = data["attributes"]["name"]
			kind = data["attributes"]["kind"]

		pm = self.tree.get_icon(kind, name).pixmap(self.preview_size)
		self.image_space.setPixmap(pm)

		if kind  == "file":
			self.set_file_properties(data)
		else:
			self.set_folder_properties(data)

	def __selection_changed(self):
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
			return

	def handle_login(self):
		pass

	def handle_logout(self):
		""" Callback function for EventDispatcher when a logout event is detected """
		self.image_space.setPixmap(QtGui.QPixmap())
		for label,value in self.properties.values():
			value.setText("")

	### Other callback functions

	def set_image_preview(self, img_content):
		self.current_img_preview = QtGui.QPixmap()
		self.current_img_preview.loadFromData(img_content)
		pixmap = self.current_img_preview.scaledToHeight(self.image_space.height())
		self.spinner.hide()
		self.image_space.setPixmap(pixmap)


class ProjectTree(QtWidgets.QTreeWidget):
	""" A tree representation of projects and files on the OSF for the current user
	in a treeview widget"""

	def __init__(self, manager, use_theme=False, \
				theme_path='./resources/iconthemes'):
		""" Constructor
		Creates a tree showing the contents of the user's OSF repositories.
		Can be passed a theme to use for the icons, but if this doesn't happen
		it will use the default qtawesome (FontAwesome) icons.

		Parameters
		----------
		use_theme : string (optional)
			The name of the icon theme to use.
		"""
		super(ProjectTree, self).__init__()

		self.manager = manager

		# Check for argument specifying that qt_theme should be used to
		# determine icons. Defaults to False.

		if type(use_theme) == str:
			self.use_theme = use_theme
			logging.info('Using icon theme of {}'.format(use_theme))
			QtGui.QIcon.setThemeName(use_theme)
			# Win and OSX don't support native themes
			# so set the theming dir explicitly
			if platform.system() in ['Darwin','Windows']:
				QtGui.QIcon.setThemeSearchPaths(QtGui.QIcon.themeSearchPaths() \
					+ [theme_path])
				logging.info(QtGui.QIcon.themeSearchPaths())
		else:
			self.use_theme = False

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

		self.setIconSize(QtCore.QSize(20,20))

	def __set_expanded_icon(self,item):
		if item.data['type'] == 'files' and item.data['attributes']['kind'] == 'folder':
			item.setIcon(0,self.get_icon('folder-open',item.data['attributes']['name']))

	def __set_collapsed_icon(self,item):
		if item.data['type'] == 'files' and item.data['attributes']['kind'] == 'folder':
			item.setIcon(0,self.get_icon('folder',item.data['attributes']['name']))

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
		QIcon : The icon for the current file/object type """

		providers = {
			'osfstorage'   : osf_logo_path,
			'github'       : 'github',
			'dropbox'      : 'dropbox',
			'googledrive'  : 'google',
		}

		if datatype == 'project':
			return QtGui.QIcon.fromTheme(
				'gbrainy',
				QtGui.QIcon(osf_logo_path)
			)

		if datatype in ['folder','folder-open']:
			# Providers are also seen as folders, so if the current folder
			# matches a provider's name, simply show its icon.
			if name in providers:
				return QtGui.QIcon(providers[name])
			else:
				return QtGui.QIcon.fromTheme(
					datatype,
					QtGui.QIcon(osf_logo_path)
				)
		elif datatype == 'file':
			# check for OpenSesame extensions first. If this is not an OS file
			# use fileinspector to determine the filetype
			if check_for_opensesame_file(name):
				filetype = 'opera-widget-manager'
			else:
				filetype = fileinspector.determine_type(name,'xdg')

			return QtGui.QIcon.fromTheme(
				filetype,
				QtGui.QIcon(osf_logo_path)
			)
		return QtGui.QIcon(osf_logo_path)


	def populate_tree(self, data, parent=None):
		"""
		Populates the tree with content retrieved from a certain entrypoint,
		specified as an api endpoint of the OSF, such a a project or certain
		folder inside a project. The JSON representation that the api endpoint
		returns is used to build the tree contents.

		Parameters
		----------
		entrypoint : string
			uri to the OSF api from where the
		parent : QtWidgets.QTreeWidgetItem (options)
			The parent item to which the generated tree should be attached.
			Is mainly used for the recursiveness that this function implements.
			If not specified the invisibleRootItem() is used as a parent.

		Returns
		-------
		list : The list of tree items that have just been generated """

		osf_response = json.loads(data.data().decode())

		if parent is None:
			parent = self.invisibleRootItem()

		for entry in osf_response["data"]:
			if entry['type'] == 'nodes':
				name = entry["attributes"]["title"]
				kind = entry["attributes"]["category"]
			if entry['type'] == 'files':
				name = entry["attributes"]["name"]
				kind = entry["attributes"]["kind"]

			values = [name,kind]
			if "size" in entry["attributes"] and entry["attributes"]["size"]:
				values += [humanize.naturalsize(entry["attributes"]["size"])]

			item = QtWidgets.QTreeWidgetItem(parent,values)

			icon = self.get_icon(kind, name)
			item.setIcon(0,icon)
			item.data = entry

			if kind in ["project","folder"]:
				try:
					next_entrypoint = entry['relationships']['files']\
						['links']['related']['href']
				except AttributeError as e:
					raise osf.OSFInvalidResponse("Invalid api call for getting next"
						"entry point: {}".format(e))
				self.manager.get(next_entrypoint, self.populate_tree, item)

	def process_repo_contents(self, logged_in_user):
		# If this function is called as a callback, the supplied data will be a
		# QByteArray. Convert to a dictionary for easier usage
		if type(logged_in_user) == QtCore.QByteArray:
			logged_in_user = json.loads(logged_in_user.data().decode())

		# Get url to user projects. Use that as entry point to populate the project tree
		try:
			user_nodes_api_call = logged_in_user['data']['relationships']['nodes']\
			['links']['related']['href']
		except AttributeError as e:
			raise osf.OSFInvalidResponse(
				"The structure of the retrieved data seems invalid: {}".format(e)
			)

		self.manager.get(user_nodes_api_call, self.populate_tree)

	# Event handling functions required by EventDispatcher

	def handle_login(self):
		""" Callback function for EventDispatcher when a login event is detected """
		if self.manager.logged_in_user != {}:
			# If manager has the data of the logged in user saved locally, pass it
			# to get_repo_contents directly.
			self.process_repo_contents(self.manager.logged_in_user)
		else:
			# If not, query the osf for the user data, and pass get_repo_contents
			# ass the callback to which the received data should be sent.
			self.manager.get_logged_in_user(self.process_repo_contents)

	def handle_logout(self):
		""" Callback function for EventDispatcher when a logout event is detected """
		self.clear()

















