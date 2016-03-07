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

from openscienceframework.settings import client_id, redirect_uri

# Convenience reference
TokenExpiredError = requests_oauthlib.oauth2_session.TokenExpiredError

class OSFInvalidResponse(Exception):
	pass

#%%------------------ Main configuration and helper functions ------------------

def reset_session():
	""" Creates/resets and OAuth 2 session, with the specified data. """
	global client_id
	global redirect_uri

	# Set up requests_oauthlib object
	mobile_app_client = MobileApplicationClient(client_id)

	# Create an OAuth2 session for the OSF
	session = requests_oauthlib.OAuth2Session(
		client_id,
		mobile_app_client,
		scope="osf.full_write",
		redirect_uri=redirect_uri,
	)
	return session

# Create an intial session object
session = reset_session()

# Generate correct URLs
base_url = "https://test-accounts.osf.io/"
auth_url = base_url + "oauth2/authorize"
token_url = base_url + "oauth2/token"
logout_url = base_url + "oauth2/revoke"

# API configuration settings
api_base_url = "https://test-api.osf.io/v2/"

api_calls = {
	"logged_in_user":"users/me",
	"projects":"users/me/nodes",
	"project_repos":"nodes/{}/files",
	"repo_files":"nodes/{}/files/{}",
}

def api_call(command, *args):
	""" generates and api endpoint. If arguments are required to build the endpoint, the can be
	specified as extra arguments.

	Parameters
	----------
	command : string
		The key of the endpoint to look up in the api_calls dictionary
	*args : various (optional)
		Optional extra data which is needed to construct the correct api endpoint uri

	Returns
	-------
	string : The complete uri for the api endpoint
	"""
	return api_base_url + api_calls[command].format(*args)

#%%--------------------------- Oauth communiucation ----------------------------

def get_authorization_url():
	""" Generate the URL at which an OAuth2 token for the OSF can be requested
	with which OpenSesame can be allowed access to the user's account.

	Returns
	-------
	string : The complete uri for the api endpoint
	"""
	return session.authorization_url(auth_url)

def parse_token_from_url(url):
	""" Parse token from url fragment """
	token = session.token_from_fragment(url)
	# Call logged_in function to notify event listeners that user is logged in
	if is_authorized():
		return token
	else:
		logging.debug("ERROR: Token received, but user not authorized")

def is_authorized():
	""" Convenience function simply returning OAuth2Session.authorized. """
	return session.authorized

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
		if session.token["expires_at"] < time.time():
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
	""" Logs out the user, and resets the global session object. """
	global session
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
	return session.get(api_call("logged_in_user"))

@requires_authentication
def get_user_projects():
	return session.get(api_call("projects"))

@requires_authentication
def get_project_repos(project_id):
	return session.get(api_call("project_repos",project_id))

@requires_authentication
def get_repo_files(project_id, repo_name):
	return session.get(api_call("repo_files",project_id, repo_name))

@requires_authentication
def direct_api_call(api_call):
	return session.get(api_call)

if __name__ == "__main__":
	print(get_authorization_url())






