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

# Module for easy OAuth2 usage, based on the requests library,
# which is the easiest way to perform HTTP requests.

# OAuth2Session
import requests_oauthlib
# Mobile application client that does not need a client_secret
from oauthlib.oauth2 import MobileApplicationClient
# Easier function decorating
from functools import wraps

# Convenience reference
TokenError = requests_oauthlib.oauth2_session.TokenExpiredError

#%%------------------ Main configuration and helper functions ------------------

client_id = "cbc4c47b711a4feab974223b255c81c1"
redirect_uri = "https://www.getpostman.com/oauth2/callback"

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

def logged_in():
	""" Function contents to be set in main module. """
	logging.warning("User logged in! Overwrite this callback function withy your own custom one")

def logged_out():
	""" Function contents to be set in main module. """
	logging.warning("User logged out! Overwrite this callback function withy your own custom one")

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
		logged_in()
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
			raise TokenError("The supplied token has expired")
			
		response = func(*args, **kwargs)
		
		# See if you can decode the response to json. This is not always the case
		# for instance, a logout request is an empty HTTP (204) response which results
		# in JSON decode error
		try:
			response = response.json()
		except Exception as e:
			logging.info("Could not decode response to JSON: {}".format(e))
			raise e
		
		# If json decoding succeeded, response is now a dict instead of a 
		# HTTP responses class
		if type(response) == dict:
			# If response contains an error key, something is wrong.
			if "errors" in response.keys():
				try:
					msg = response['errors'][0]['detail']
				except AttributeError:
					raise Exception('An error occured, but OSF error message \
						could not be retrieved. Invalid format?')
				# Check if message involves an incorrecte token response
				if msg == "User provided an invalid OAuth2 access token":
					raise TokenError(msg)
				# If not, the error is undefined, unexpected and potentially serious,
				# so raise as a general exception
				else:
					raise Exception(msg)
		return response
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
		logged_out()
	else:
		logging.debug("Error logging out")
	return resp
	
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
	
	
	
	


