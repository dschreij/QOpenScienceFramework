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
import inspect
import logging
import os
import json


class EventDispatcher(object):
	"""The event dispatcher fires events to connected classes, which are henceforth
	referenced to as 'listeners'. Basically EventDispatcher's purpose is
	to propagate login and logout events to the QWidget subclasses that require 
	authorization at the OSF to function correctly, but of course this can be extended
	with events that are relevant for all listeners.

	The only requirement for listener classes is that they implement a handling 
	function for each event that is present in the self.events list.
	These functions should be named "handle_<event_name>". For example, to catch
	a login event, a listener should have the function handle_login. Each listener
	has to have handle functions for *all* events specified in the self.events list."""
	
	# List of possible events this dispatcher can emit
	events = ["login","logout"]	
	
	def __init__(self):
		""" Constructor """
		super(EventDispatcher, self).__init__()
		self.__listeners = []
	
	def __check_events(self,item):
		"""Checks if the passed object has the required handler functions.
		Args:
			item - the object to check
		Raises:
			NameError - if the object does not have the required event handling 
			functions
		"""
		for event in self.events:
			if not hasattr(item,"handle_"+event) or not inspect.ismethod(getattr(item,"handle_"+event)):
				raise NameError("{} does not have the required function {}".\
					format(item.__class__.__name__, "handle_"+event))
	
	def add(self, obj):
		""" Add (a) new object(s) to the list of objects listening for the events 
	
		Args:
			obj - the listener to add. Can be a single listener or a list of listeners.
		"""
		# If the object passed is a list, check if each object in the list has the
		# required event handling functions
		if type(obj) == list:
			for item in obj:
				self.__check_events(item)
			self.__listeners.extend(obj)
		else:
		# If a single object is passed, check if it has the required functions
			self.__check_events(obj)
			self.__listeners.append(obj)
		return self
			
	def remove(self,obj):
		""" Remove a listener. Can be provided as a reference to the object
		or simply by an index """
		for item in self.__listeners:
			# Delete by object reference
			if obj is item:
				del self.__listeners[self.__listeners.index(item)]
			# Delete by index
			if type(obj) == int:
				del self.__listeners[obj]
		return self
			
	def get_listeners(self):
		return self.__listeners
		
	def dispatch_login(self):
		""" Convenience function to dispatch the login event """
		self.dispatch("login")
		
	def dispatch_logout(self):
		""" Convenience function to dispatch the logout event """
		self.dispatch("logout")
		
	def dispatch(self,event):
		""" Dispatch an event specified by the passed argument. The event has
		to occur in the self.events list, otherwise an exception is raised."""
		
		if not event in self.events:
			raise ValueError("Unknown event '{}'".format(event))
			
		for item in self.__listeners:
			# Check here again, just to be sure
			if not hasattr(item,"handle_"+event) or not inspect.ismethod(getattr(item,"handle_"+event)):
				raise NameError("{} does not have the required function {}".\
					format(item.__name__, "handle_"+event))
			# Call the function!
			getattr(item,"handle_"+event)()	
			
class TestListener(object):
	def handle_login(self):
		logging.info("Login event received")
		
	def handle_logout(self):
		logging.info("Logout event received")

		
class TokenFileListener(object):
	def __init__(self,tokenfile,osf):
		super(TokenFileListener,self).__init__()
		self.tokenfile = tokenfile
		self.osf=osf
	
	def handle_login(self):
		if self.osf.session.token:
			tokenstr = json.dumps(self.osf.session.token)
			with open(self.tokenfile,'w') as f:
				f.write(tokenstr)
		else:
			logging.error("Error, could not find authentication token")

	def handle_logout(self):
		if os.path.isfile(self.tokenfile):
			try:
				os.remove(self.tokenfile)
			except Exception as e:
				logging.warning("WARNING: {}".format(e.message))
				
		
if __name__== "__main__":
	""" Test the dispatcher """
	dispatcher = EventDispatcher()
	tl = TestListener() # To be removed later	
	dispatcher.add(tl)
	
	for event in dispatcher.events:
		dispatcher.dispatch(event)
	