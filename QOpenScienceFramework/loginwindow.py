# -*- coding: utf-8 -*-

# Python3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging
logging.basicConfig(level=logging.INFO)

# QT classes
# Required QT classes
from qtpy import QtCore

# QtWebKit is dropped in favour of QtWebEngine from Qt 5.6 on
try:
	from qtpy.QtWebKit import QWebView as WebView
except ImportError:
	from qtpy.QtWebEngineWidgets import QWebEngineView as WebView

# OSF connection interface
import QOpenScienceFramework.connection as osf
# Python 2 and 3 compatiblity settings
from QOpenScienceFramework.compat import *
from QOpenScienceFramework import dirname

osf_logo_path = os.path.join(dirname, 'img/cos-white2.png')

# Dummy function later to be replaced for translation
_ = lambda s: s

class LoginWindow(WebView):
	""" A Login window for the OSF """
	
	# Login event is emitted after successfull login
	logged_in = QtCore.Signal()
	""" Event fired when user successfully logged in. """

	def __init__(self, *args, **kwargs):
		super(LoginWindow, self).__init__(*args, **kwargs)

		try:
			# Create Network Access Manager to listen to all outgoing
			# HTTP requests. Necessary to work around the WebKit 'bug' which
			# causes it drop url fragments, and thus the access_token that the
			# OSF Oauth system returns
			self.nam = self.page().networkAccessManager()

			# Connect event that is fired if a HTTP request is completed.
			self.nam.finished.connect(self.checkResponse)
		except:
			pass
			# Connect event that is fired if a HTTP request is completed.
			# self.finished.connect(self.checkResponse)

		# Connect event that is fired after an URL is changed
		# (does not fire on 301 redirects, hence the requirement of the NAM)
		self.urlChanged.connect(self.check_URL)

	def checkResponse(self, reply):
		"""Callback function. Do not use directly. 

		Callback for NetworkRequestManager.finished event
		used to check if OAuth2 is redirecting to a link containing the token
		string. This is necessary for the QtWebKit module, because it drops
		fragments after being redirect to a different URL. QWebEngine uses the
		check_URL function to check for the token fragment

		Parameters
		----------
		reply : QtNetwork.QNetworkReply
			The response object provided by NetworkRequestManager
		"""
		request = reply.request()
		# Get the HTTP statuscode for this response
		statuscode = reply.attribute(request.HttpStatusCodeAttribute)
		# The accesstoken is given with a 302 statuscode to redirect

		# Stop if statuscode is not 302 (HTTP Redirect)
		if statuscode != 302:
			return

		redirectUrl = reply.attribute(request.RedirectionTargetAttribute)
		if not redirectUrl.hasFragment():
			return

		r_url = redirectUrl.toString()
		if osf.settings['redirect_uri'] in r_url:
			try:
				self.token = osf.parse_token_from_url(r_url)
			except ValueError as e:
				logging.warning(e)
			else:
				self.logged_in.emit()
				self.hide()

	def check_URL(self, url):
		""" Callback function. Do not use directly.
		
		Calback for urlChanged event.

		Parameters
		----------
		command : url
			New url, provided by the urlChanged event

		"""
		url_string = url.toString()

		# QWebEngineView receives token here.
		if url.hasFragment():
			try:
				self.token = osf.parse_token_from_url(url_string)
			except ValueError as e:
				logging.warning(e)
			else:
				self.logged_in.emit()
				self.hide()
