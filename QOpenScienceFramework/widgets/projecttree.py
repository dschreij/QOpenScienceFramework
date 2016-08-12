# -*- coding: utf-8 -*-

# Python3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import json
import logging
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
# Unix style filename matching
import fnmatch
# QT classes
# Required QT classes
from qtpy import QtGui, QtCore, QtWidgets, QtNetwork

import pprint
pp = pprint.PrettyPrinter(indent=2)

# Python 2 and 3 compatiblity settings
from QOpenScienceFramework.compat import *

from QOpenScienceFramework.util import check_if_opensesame_file
from QOpenScienceFramework import dirname


osf_logo_path = os.path.join(dirname, 'img/cos-white2.png')
osf_blacklogo_path = os.path.join(dirname, 'img/cos-black.png')

# Dummy function later to be replaced for translation
_ = lambda s: s

class ProjectTree(QtWidgets.QTreeWidget):
	""" A tree representation of projects and files on the OSF for the current user
	in a treeview widget."""

	# Event fired when refresh of tree is finished
	refreshFinished = QtCore.Signal()
	""" PyQt signal that emits when the tree is completely refreshed. """
	# Maximum of items to return per request (e.g. files in a folder). OSF 
	# automatically paginates its results
	ITEMS_PER_PAGE = 50

	def __init__(self, manager, use_theme=None, theme_path='./resources/iconthemes'):
		""" Constructor.
		Creates a tree showing the contents of the user's OSF repositories.
		Can be passed a theme to use for the icons, but if this doesn't happen
		it will use the default qtawesome (FontAwesome) icons for the buttons.

		Parameters
		----------
		manager : manger.ConnectionManager
			The object taking care of all the communication with the OSF.
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
		""" The currently set filter parameters. """
		return self._filter

	@filter.setter
	def filter(self, value):
		""" Sets a filter for items present in the tree. Only shows tree items 
		that match the specified file extension(s) and hides the others.

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
		""" Sets an extension based filter for items in the tree.

		.. note :: Can be used instead of using ProjectTree.filter = <value> directly.
		
		Parameters
		----------
		filetypes : str or list
			A filetype or list of filetypes that should be shown while other file
			types are hidden. For example, passing '.txt' to this function will
			only show files which have the .txt extension
		"""
		self.filter = filetypes

	def clear_filter(self):
		""" Clears the filter. """
		self.filter = None

	def find_item(self, item, index, value):
		""" Finds an item in the tree.
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
		int
			The index position at which the item is found or None .
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
		""" Returns a QIcon for the passed datatype.
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
		QtGui.QIcon
			The icon for the current file/object type """

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
		""" Refreshes the children of the specified node.
		In contrast to refresh_contents, which refreshes the whole tree from
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
		""" Refreshes all contents in the tree. This operation might take a long
		time depending on the number of projects that the user has, so it is 
		recommended to use a partial refresh (refresh_children_of_node), wherever
		you can. """
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
		""" Adds a new item to the tree. The data that is passed should be
		the dictionary containing the information that is found under the 'data'
		key in an OSF API responses.
	
		Parameters
		----------
		parent : QtWidgets.QTreeWidgetItem
			The parent node to place the new item under.
		data : dict
			The 'data' segment from the osf data.

		Returns
		-------
		item : QtWidgets.QTreeWidgetItem
			The newly created tree widget item
		kind : str
			The type of the new item (folder, file, project, etc.)
		"""
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
		Populates the tree with content. The entry point should be a project, 
		repository or folder inside a repository. The JSON representation 
		that the api endpoint returns for such a node is used to build the tree 
		contents. This function is called recursively, for each new subfolder that
		is encountered from the entry point on.

		Parameters
		----------
		reply : QtNetwork.QNetworkReply
			The data of the entrypoint from the OSF to create the node in the 
			tree for. 
		parent : QtWidgets.QTreeWidgetItem (default: None)
			The parent item to which the generated tree should be attached.
			Is mainly used for the recursiveness that this function implements.
			If not specified the invisibleRootItem() is used as a parent.

		Returns
		-------
		list
			The list of tree items that have just been generated """

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
				# another event deleted treeWidgetItems. Not much that can be
				# done here, so do some cleanup and quit
				warnings.warn(str(e))
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
		""" Callback function for EventDispatcher when a login event is detected. """
		self.active_requests = []
		self.refresh_contents()

	def handle_logout(self):
		""" Callback function for EventDispatcher when a logout event is detected. """
		self.active_requests = []
		self.previously_selected_item = None
		self.clear()
