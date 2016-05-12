# -*- coding: utf-8 -*-
"""
This module handles the OAuth2 authentication process and maintains the
session (/token) information that is required to communicate with the OSF API

It is also responsible for constructing the correct API calls/uris as specified by the
OSF for the various types of information that can be requested.

.. Note:: A lot of the functions that are available here have equivalents in the
	ConnectionManager class. It is recommended to use those functions instead as they are
	executed asynchronously and are used throughout the rest of the application.
"""

# Python3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from QOpenScienceFramework.compat import *

# Import basics
import os
import time
import logging
import json

# Module for easy OAuth2 usage, based on the requests library,
# which is the easiest way to perform HTTP requests.

# OAuth2Session
import requests_oauthlib
# Mobile application client that does not need a client_secret
from oauthlib.oauth2 import MobileApplicationClient
# Easier function decorating
from functools import wraps
from QOpenScienceFramework import dirname

# Load settings file containing required OAuth2 parameters
with open(os.path.join(dirname, 'settings.json')) as fp:
	settings = json.load(fp)
base_url = settings['base_url']
api_base_url = settings['api_base_url']
scope = settings['scope']
website_url = settings['website_url']

# Convenience reference
TokenExpiredError = requests_oauthlib.oauth2_session.TokenExpiredError

class OSFInvalidResponse(Exception):
	pass

session = None

#%%------------------ Main configuration and helper functions ------------------

def create_session():
	""" Creates/resets and OAuth 2 session, with the specified data. """
	global session
	global settings

	try:
		client_id = settings['client_id']
		redirect_uri = settings['redirect_uri']
	except KeyError as e:
		raise KeyError("The OAuth2 settings dictionary is missing the {} entry. "
			"Please add it to the QOpenScienceFramework.connection.settings "
			"dicationary before trying to create a new session".format(e))

	# Set up requests_oauthlib object
	mobile_app_client = MobileApplicationClient(client_id)

	# Create an OAuth2 session for the OSF
	session = requests_oauthlib.OAuth2Session(
		client_id,
		mobile_app_client,
		scope=scope,
		redirect_uri=redirect_uri,
	)
	return session

# Generate correct URLs
auth_url = base_url + "oauth2/authorize"
token_url = base_url + "oauth2/token"
logout_url = base_url + "oauth2/revoke"

# API configuration settings
api_calls = {
	"logged_in_user":"users/me/",
	"projects":"users/me/nodes/",
	"project_repos":"nodes/{}/files/",
	"repo_files":"nodes/{}/files/{}/",
	"file_info":"files/{}/",
}

def api_call(command, *args):
	""" generates and api endpoint. If arguments are required to build the endpoint
	, they can be specified as extra arguments.

	Parameters
	----------
	command : {'logged_in_user', 'projects', 'project_repos', 'repo_files', 'file_info'}
		The key of the endpoint to look up in the api_calls dictionary
	
		Extra arguments passed to this function will be integrated into the API call \
		at specified positions (marked by \{\}). The formats of the calls are as follows:

			``logged_in_user: "users/me/"``

			``projects: "users/me/nodes/"``
			
			``project_repos: "nodes/{}/files/"``

			``repo_files: "nodes/{}/files/{}/"``

			``file_info: "files/{}/"``

	*args : various (optional)
		Optional extra data which is needed to construct the correct api endpoint uri. \
		Check the OSF API documentation for a list of variables that each type of \
		call expects.

	Returns
	-------
	string : The complete uri for the api endpoint.
	"""

	return api_base_url + api_calls[command].format(*args)

def check_for_active_session():
	""" Checks if a session object has been created and raises a RuntimeError otherwise."""
	if session is None:
		raise RuntimeError("Session is not yet initialized, use connection."
			"session = connection.create_session()")


#%%--------------------------- Oauth communiucation ----------------------------


def get_authorization_url():
	""" Generate the URL at which an OAuth2 token for the OSF can be requested
	with which OpenSesame can be allowed access to the user's account.

	Returns
	-------
	str
		The complete uri for the api endpoint.

	Raises
	------
	RuntimeError
		When there is no active OAuth2 session.
	"""
	check_for_active_session()
	return session.authorization_url(auth_url)

def parse_token_from_url(url):
	""" Parses token from url fragment 

	Parameters
	----------
	url : str
		The url to parse. Should have a hass fragment (#) after which the token
		information is found.

	Returns
	-------
	str
		The currently used OAuth2 access token.

	Raises
	------
	RuntimeError
		When there is no active OAuth2 session.
	"""
	check_for_active_session()
	token = session.token_from_fragment(url)
	# Call logged_in function to notify event listeners that user is logged in
	if is_authorized():
		return token
	else:
		logging.debug("ERROR: Token received, but user not authorized")


def is_authorized():
	""" Convenience function simply returning OAuth2Session.authorized. 

	Returns
	-------
	bool
		True is the user is authorized, False if not
	"""
	check_for_active_session()
	return session.authorized

def token_valid():
	""" Checks if OAuth token is present, and if so, if it has not expired yet. 

	Returns
	-------
	bool
		True if the token is present and is valid, False otherwise

	"""
	check_for_active_session()
	if not hasattr(session,"token") or not session.token:
		return False
	return session.token["expires_at"] > time.time()

def requires_authentication(func):
	""" Decorator function which checks if a user is authenticated before he
	performs the desired action. It furthermore checks if the response has been
	received without errors."""

	@wraps(func)
	def func_wrapper(*args, **kwargs):
		# Check first if a token is present in the first place
		if not is_authorized():
			print("You are not authenticated. Please log in first.")
			return False
		# Check if token has not yet expired
		if not token_valid():
			raise TokenExpiredError("The supplied token has expired")

		response = func(*args, **kwargs)

		# Check response status code to be 200 (HTTP OK)
		if response.status_code == 200:
			# Check if response is JSON format
			if response.headers['content-type'] == 'application/vnd.api+json':
				# See if you can decode the response to json.
				try:
					response = response.json()
				except json.JSONDecodeError as e:
					raise OSFInvalidResponse(
						"Could not decode response to JSON: {}".format(e))
				return response
			# Check if response is an octet stream (binary data format)
			# and if so, return the raw content since its probably a download.
			if response.headers['content-type'] == 'application/octet-stream':
				return response.content
		# Anything else than a 200 code response is probably an error
		if response.headers['content-type'] in ['application/json','application/vnd.api+json']:
			# See if you can decode the response to json.
			try:
				response = response.json()
			except json.JSONDecodeError as e:
				OSFInvalidResponse("Could not decode response to JSON: {}".format(e))

			if "errors" in response.keys():
				try:
					msg = response['errors'][0]['detail']
				except AttributeError:
					raise OSFInvalidResponse('An error occured, but OSF error \
						message could not be retrieved. Invalid format?')
				# Check if message involves an incorrecte token response
				if msg == "User provided an invalid OAuth2 access token":
					logout()
					raise TokenExpiredError(msg)

		# If no response has been returned by now, or no error has been raised,
		# then something fishy is going on that should be reported as en Error

		# Don't print out html pages or octet stream, as this is useless
		if not response.headers['content-type'] in ["text/html","application/octet-stream"]:
			message = response.content
		else:
			message = ""

		error_text = 'Could not handle response {}: {}\nContent Type: {}\n{}'.format(
			response.status_code,
			response.reason,
			response.headers['content-type'],
			message
		)
		raise OSFInvalidResponse(error_text)
	return func_wrapper

def logout():
	""" Logs out the user, and resets the global session object. 

	Returns
	-------
	bool
		True if logout was succesful, False if not.

	"""
	global session
	check_for_active_session()
	resp = session.post(logout_url,{
		"token": session.access_token
	})
	# Code 204 (empty response) signifies success
	if resp.status_code == 204:
		logging.info("User logged out")
		# Reset session object
		session = reset_session()
		return True
	else:
		logging.debug("Error logging out")
		return False

#%% Functions interacting with the OSF API

@requires_authentication
def get_logged_in_user():
	""" Gets the currently logged in user's data 

	Returns
	-------
	dict
		The dict containing the returned JSON data
	"""
	return session.get(api_call("logged_in_user"))

@requires_authentication
def get_user_projects():
	""" Gets the currently logged in user's projects

	Returns
	-------
	dict
		The dict containing the returned JSON data
	"""
	return session.get(api_call("projects"))

@requires_authentication
def get_project_repos(project_id):
	""" Gets the data of the specified project

	Parameters
	----------
	project_id : str
		Reference to the project node on the OSF

	Returns
	-------
	dict
		The dict containing the returned JSON data
	"""
	return session.get(api_call("project_repos",project_id))

@requires_authentication
def get_repo_files(project_id, repo_name):
	""" Gets the data of the specified repository of the specified project.

	Parameters
	----------
	project_id : str
		Reference to the project node on the OSF
	repo_name : {'osfstorage','dropbox','github','figshare','s3','googledrive'}
		The repository to return the data of.

	Returns
	-------
	dict
		The dict containing the returned JSON data
	"""
	return session.get(api_call("repo_files",project_id, repo_name))

@requires_authentication
def direct_api_call(api_call):
	""" Performs a direct api call. Can be used as the api call is already 
	constructed.

	Parameters
	----------
	api_call: str
		The api call to perform

	Returns
	-------
	dict
		The dict containing the returned JSON data
	"""
	return session.get(api_call)

if __name__ == "__main__":
	print(get_authorization_url())
