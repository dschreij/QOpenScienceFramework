# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from QOpenScienceFramework import dirname
from QOpenScienceFramework.util import check_if_opensesame_file
from QOpenScienceFramework.compat import *
from qtpy import QtGui, QtCore, QtWidgets, QtNetwork

import pprint
import fnmatch
import humanize
import arrow
import fileinspector
import QOpenScienceFramework.connection as osf
import qtawesome as qta
import os
import json
import logging
import warnings

logger = logging.getLogger()
pp = pprint.PrettyPrinter(indent=2)

osf_logo_path = os.path.join(dirname, 'img/cos-white2.png')
osf_blacklogo_path = os.path.join(dirname, 'img/cos-black.png')


def _(s):
    """ Dummy function later to be replaced for translation """
    return s


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
                QtGui.QIcon.setThemeSearchPaths(QtGui.QIcon.themeSearchPaths()
                                                + [theme_path])

        # Set up general window
        self.resize(400, 500)

        # Set Window icon
        if not os.path.isfile(osf_logo_path):
            logger.error("OSF logo not found at {}".format(osf_logo_path))
        osf_icon = QtGui.QIcon(osf_logo_path)
        self.setWindowIcon(osf_icon)

        # Set column labels
        self.setHeaderLabels([_("Name"), _("Kind"), _("Size"), _("Created"),
                              _("Modified")])
        self.setColumnWidth(0, 300)

        # Event handling
        self.itemExpanded.connect(self.__set_expanded_icon)
        self.itemExpanded.connect(self.__fetch_if_needed)
        self.itemCollapsed.connect(self.__set_collapsed_icon)
        self.refreshFinished.connect(self.__refresh_finished)

        # Items currently expanded
        self.expanded_items = set()

        # Set icon size for tree items
        self.setIconSize(QtCore.QSize(20, 20))

        # Due to the recursive nature of the tree populating function, it is
        # sometimes difficult to keep track of if the populating function is still
        # active. This is a somewhat hacky attempt to artificially keep try to keep
        # track, by adding current requests in this list.
        self.active_requests = []

        # Init filter variable
        self.__filter = None

        # Save the previously selected item before a refresh, so this item can
        # be set as the selected item again after the refresh
        self.previously_selected_item = None

        # Flag that indicates if contents are currently refreshed
        self.isRefreshing = False

        # The icon to show for refreshing items
        self.refresh_icon = qta.icon('fa.refresh', color='green')

    # Private functions

    def __set_expanded_icon(self, item):
        data = item.data(0, QtCore.Qt.UserRole)
        if data['type'] == 'files' and data['attributes']['kind'] == 'folder':
            item.setIcon(0, self.get_icon(
                'folder-open', data['attributes']['name']))
        self.expanded_items.add(data['id'])

    def __set_collapsed_icon(self, item):
        data = item.data(0, QtCore.Qt.UserRole)
        if data['type'] == 'files' and data['attributes']['kind'] == 'folder':
            item.setIcon(0, self.get_icon(
                'folder', data['attributes']['name']))
        self.expanded_items.discard(data['id'])

    def __fetch_if_needed(self, item):
        data = item.data(0, QtCore.Qt.UserRole)
        nodeStatus = item.data(1, QtCore.Qt.UserRole)
        if (data['type'] == 'nodes' or data['attributes']['kind'] == 'folder') \
                and not nodeStatus['fetched']:
            self.refresh_children_of_node(item)

    def __cleanup_reply(self, reply, *args, **kwargs):
        """ Callback for when an error occured while populating the tree, or when
        populate_tree finished successfully. Removes the QNetworkReply
        from the list of active HTTP operations. """
        # Reset active requests after error
        try:
            self.active_requests.remove(reply)
        except ValueError:
            logger.info("Reply not found in active requests")

        # reset the loading icon to the item's original, if necessary
        if len(args) and type(args[0]) == QtWidgets.QTreeWidgetItem:
            nodeStatus = args[0].data(1, QtCore.Qt.UserRole)
            if not nodeStatus is None:
                args[0].setIcon(0, nodeStatus['icon'])

        reply.deleteLater()
        if not self.active_requests:
            self.refreshFinished.emit()

    def __refresh_finished(self):
        """ Expands all treewidget items again that were expanded before the
        refresh. """

        # Reapply filter if set
        if self.__filter:
            self.filter = self.__filter

        iterator = QtWidgets.QTreeWidgetItemIterator(self)
        while(iterator.value()):
            item = iterator.value()
            item_data = item.data(0, QtCore.Qt.UserRole)
            if item_data['id'] in self.expanded_items:
                item.setExpanded(True)
            # Reset selection to item that was selected before refresh
            if self.previously_selected_item:
                if self.previously_selected_item['id'] == item_data['id']:
                    self.setCurrentItem(item)
            iterator += 1

        self.isRefreshing = False
    # Properties

    @property
    def filter(self):
        """ The currently set filter parameters. """
        return self.__filter

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
        self.__filter = value

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
                if self.__filter is None:
                    item.setHidden(False)
                    iterator += 1
                    continue

                # Check if filter extension is contained in filename
                item_data = item.data(0, QtCore.Qt.UserRole)
                filename = item_data['attributes']['name']

                # Assume no match by default
                typematch = False
                # If filter is a single string, just check directly
                if isinstance(self.__filter, basestring):
                    typematch = fnmatch.fnmatch(filename, self.__filter)
                # If filter is a list, compare to each item in it
                if isinstance(self.__filter, list):
                    for ext in self.__filter:
                        if fnmatch.fnmatch(filename, ext):
                            typematch = True
                            break
                # Set item's visibility according to value of typematch
                if typematch:
                    item.setHidden(False)
                else:
                    item.setHidden(True)
            iterator += 1

    # Public functions

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

        for i in range(0, child_count):
            child = item.child(i)
            displaytext = child.data(0, QtCore.Qt.DisplayRole)
            if displaytext == value:
                return i
        return None

    def get_icon(self, datatype, name):
        """ Returns a QIcon for the passed datatype.
        Retrieves the current theme icon for a certain object (project, folder)
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
            'osfstorage': osf_blacklogo_path,
            'github': 'web-github',
            'dropbox': 'dropbox',
            'googledrive': 'web-google-drive',
            'box': 'web-microsoft-onedrive',
            'cloudfiles': 'web-microsoft-onedrive',
            'dataverse': 'web-microsoft-onedrive',
            'figshare': 'web-microsoft-onedrive',
            's3': 'web-microsoft-onedrive',
        }

        if datatype.lower() in ['public project', 'private project', 'readonly project']:
            if datatype.lower() == 'public project':
                return qta.icon('fa.cube', 'fa.globe', options=[
                    {},
                    {'scale_factor': 0.75,
                     'offset': (0.2, 0.20),
                     'color': 'green'}
                ])
            elif datatype.lower() == "readonly project":
                return qta.icon('fa.cube', 'fa.lock', options=[
                    {},
                    {'scale_factor': 0.75,
                     'offset': (0.2, 0.20),
                     'color': 'red'}
                ])
            else:
                return qta.icon('fa.cube')

        if datatype in ['folder', 'folder-open']:
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
                filetype = fileinspector.determine_type(name, 'xdg')

            return QtGui.QIcon.fromTheme(
                filetype,
                QtGui.QIcon.fromTheme(
                    'text-x-generic',
                    QtGui.QIcon(osf_blacklogo_path)
                )
            )
        return QtGui.QIcon(osf_blacklogo_path)

    def refresh_children_of_node(self, node, recursive=False):
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

        try:
            # If tree currently is refreshing, do nothing
            nodeStatus = node.data(1, QtCore.Qt.UserRole)
            if nodeStatus['refreshing']:
                return
            # Set flag that tree is currently refreshing
            nodeStatus['refreshing'] = True
            node.setData(1, QtCore.Qt.UserRole, nodeStatus)

            node_data = node.data(0, QtCore.Qt.UserRole)
        except RuntimeError as e:
            warnings.warn('Partial refresh attempted while tree item was already'
                          ' deleted', e)
            return

        try:
            content_url = node_data['relationships']['files']['links']['related']['href']
        except KeyError as e:
            nodeStatus['refreshing'] = False
            raise osf.OSFInvalidResponse(
                'Invalid structure of tree item data: {}'.format(e))

        # Delete the current children of the node to make place for the new ones
        node.takeChildren()

        # Retrieve the new listing of children from the OSF
        req = self.manager.get(
            content_url,
            self.populate_tree,
            node,
            errorCallback=self.__cleanup_reply,
            recursive=recursive
        )

        # If something went wrong, req should be None
        if req:
            self.active_requests.append(req)
            self.set_loading_icon(node)

        # If recursive retrieval is enabled, the steps below will take place in populate_tree itself
        if not recursive:
            self.fetch_linked_nodes(node, recursive=recursive)


    def fetch_linked_nodes(self, node, recursive=False):
        try:
            node_data = node.data(0, QtCore.Qt.UserRole)
        except RuntimeError as e:
            warnings.warn('Partial refresh attempted while tree item was already'
                          ' deleted', e)
            return

        if node_data['type'] != 'nodes' or node_data["attributes"]["category"] != 'project':
            return
        try:
            related_url = node_data['relationships']['linked_nodes']['links']['related']['href']
            # Retrieve the new listing of children from the OSF
            related_url += "?page[size]={}".format(self.ITEMS_PER_PAGE)
            req = self.manager.get(
                related_url,
                self.populate_tree,
                node,
                errorCallback=self.__cleanup_reply,
                recursive=recursive
            )
            if req:
                self.active_requests.append(req)
        except KeyError as e:
            logger.warning('Unable to fetch related items: {}'.format(e))
            return

    def refresh_contents(self):
        """ Refreshes all contents in the tree. This operation might take a long
        time depending on the number of projects that the user has, so it is
        recommended to use a partial refresh (refresh_children_of_node), wherever
        you can. """

        # If tree is already refreshing, don't start again, as this will result
        # in a crash
        if self.isRefreshing:
            return
        # Set flag that tree is currently refreshing
        self.isRefreshing = True

        # Save current item selection to restore it after refresh
        current_item = self.currentItem()
        if current_item:
            self.previously_selected_item = current_item.data(
                0, QtCore.Qt.UserRole)
        else:
            self.previously_selected_item = None

        if self.manager.logged_in_user != {}:
            # If manager has the data of the logged in user saved locally, pass it
            # to get_repo_contents directly.
            self.process_repo_contents(self.manager.logged_in_user)
        else:
            # If not, query the osf for the user data, and pass get_repo_contents
            # as the callback to which the received data should be sent.
            self.manager.get_logged_in_user(
                self.process_repo_contents, errorCallback=self.__cleanup_reply)

    def determine_node_type(self, data):
        """ Determines the type of the node given its data.

        Parameters
        ----------
        data : dict
                The 'data' segment from the node containing the osf data.

        Returns
        -------
        name: str
                The title of the node (usually the file or folder name)
        kind : str
                The type of the new item (folder, file, project, etc.)
        icon_type: str
                The filetype to use for icon determination
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
        return name, kind, icon_type

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

        name, kind, icon_type = self.determine_node_type(data)

        values = [name, kind]
        if "size" in data["attributes"] and data["attributes"]["size"]:
            values += [humanize.naturalsize(data["attributes"]["size"])]
        else:
            values += ['']

        if "date_created" in data["attributes"]:
            cArrow = arrow.get(data["attributes"]["date_created"]).to('local')
            values += [cArrow.format('YYYY-MM-DD')]
        else:
            values += ['']

        if "date_modified" in data["attributes"]:
            mArrow = arrow.get(data["attributes"]["date_modified"]).to('local')
            values += [mArrow.format('YYYY-MM-DD')]
        else:
            values += ['']

        # Create item
        item = QtWidgets.QTreeWidgetItem(parent, values)
        if kind == 'project' or kind == 'folder':
            item.setChildIndicatorPolicy(
                QtWidgets.QTreeWidgetItem.ShowIndicator)

        # Copy permission data of project to child elements
        if kind != "project" and parent:
            try:
                parent_data = parent.data(0, QtCore.Qt.UserRole)
                if parent_data and "current_user_permissions" in parent_data["attributes"]:
                    data["attributes"]["current_user_permissions"] = \
                        parent_data["attributes"]["current_user_permissions"]
            except AttributeError as e:
                raise osf.OSFInvalidResponse(
                    "Could not obtain permission data: {}".format(e))
        elif kind == "project":
            # Show a lock icon if project has read-only permissions
            if not "write" in data["attributes"]["current_user_permissions"]:
                icon_type = "readonly project"

        # Set icon
        icon = self.get_icon(icon_type, name)
        item.setIcon(0, icon)
        # Add data
        item.setData(0, QtCore.Qt.UserRole, data)
        item.setData(1, QtCore.Qt.UserRole, {
            'refreshing': False,
            'fetched': False,
            'icon': icon
        })

        return item, kind

    def populate_tree(self, reply, parent=None, recursive=False):
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
        nodeStatus = None

        if parent is None or parent.data(0, QtCore.Qt.UserRole) is None:
            parent = self.invisibleRootItem()
        else:
            nodeStatus = parent.data(1, QtCore.Qt.UserRole)
            nodeStatus['fetched'] = True
            parent.setChildIndicatorPolicy(
                QtWidgets.QTreeWidgetItem.DontShowIndicatorWhenChildless)

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

            if kind in ["project", "folder"] and recursive:
                try:
                    next_entrypoint = entry['relationships']['files']['links']['related']['href']
                except KeyError as e:
                    raise osf.OSFInvalidResponse("Invalid api call for getting next"
                                                 "entry point: {}".format(e))
                # Add page size parameter to url to let more than 10 results per page be
                # returned
                next_entrypoint += "?page[size]={}".format(self.ITEMS_PER_PAGE)
                req = self.manager.get(
                    next_entrypoint,
                    self.populate_tree,
                    item,
                    errorCallback=self.__cleanup_reply,
                    recursive=recursive
                )
                # If something went wrong, req should be None
                if req:
                    self.active_requests.append(req)
                    self.set_loading_icon(item)

                self.fetch_linked_nodes(item, recursive)

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
        else:
            if not nodeStatus is None:
                # Reset icon of the refreshed TreeWidgetItem (in case it was set to a loading icon)
                self.reset_icon(parent)
                nodeStatus['refreshing'] = False

        if not nodeStatus is None:
            parent.setData(1, QtCore.Qt.UserRole, nodeStatus)

        # Remove current reply from list of active requests (assuming it finished)
        self.__cleanup_reply(reply)

    def set_loading_icon(self, item):
        if type(item) != QtWidgets.QTreeWidgetItem:
            return
        item.setIcon(0, self.refresh_icon)

    def reset_icon(self, item):
        """ Resets the icon of the treewidget item to its original icon.

        When a treewidget item is a container (project, folder, etc.) its icon will be set to a
        spinner or loading indicator when its contents are refreshed. This function resets the item's
        icon to its original.

        Parameters
        ----------
        item : QtWidgets.QTreeWidgetItem
                The item of which to reset the icon.
        """

        if type(item) != QtWidgets.QTreeWidgetItem:
            return
        try:
            data = item.data(1, QtCore.Qt.UserRole)
            if data is None:
                warnings.warn('node data was None, but it should not be')
                return
            item.setIcon(0, data['icon'])
        except RuntimeError as e:
            warnings.warn(str(e))
            return

    def process_repo_contents(self, logged_in_user):
        """ Processes contents for the logged in user. Starts by listing
        the projects and then recurses through all their repositories, folders and files. """
        # If this function is called as a callback, the supplied data will be a
        # QByteArray. Convert to a dictionary for easier usage
        if isinstance(logged_in_user, QtNetwork.QNetworkReply):
            logged_in_user = json.loads(
                safe_decode(logged_in_user.readAll().data()))

        # Get url to user projects. Use that as entry point to populate the project tree
        try:
            user_nodes_api_call = logged_in_user['data']['relationships']['nodes']['links']['related']['href']
        except AttributeError as e:
            raise osf.OSFInvalidResponse(
                "The structure of the retrieved data seems invalid: {}".format(
                    e)
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
        if not self.isRefreshing:
            self.refresh_contents()

    def handle_logout(self):
        """ Callback function for EventDispatcher when a logout event is detected. """
        self.active_requests = []
        self.previously_selected_item = None
        self.clear()
