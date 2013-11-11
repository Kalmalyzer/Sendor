
import json
import logging
import os
import unittest

from SendorJob import SendorAction

import target_distribution_methods

import target_distribution_method_cp
import target_distribution_method_sftp
import target_distribution_method_parallel_sftp

distribution_logger = logging.getLogger('main.distribution')

class LogDistributionAction(SendorAction):
	def __init__(self, type, filename, target):
		self.description = type
		self.filename = filename
		self.target = target

	def run(self, context):
		distribution_logger.info(self.description + " distribution of " + self.filename + " to " + self.target['name'])


class Targets(object):

	def __init__(self, targets):
		self.targets = targets

	def create_distribution_actions(self, source, filename, sha1sum, size, id):
		if not id in self.targets:
			raise Exception("id " + id + " does not exist in targets")

		target = self.targets[id]
		actions = []
		actions.append(LogDistributionAction("Started", filename, target))
		actions.extend(target_distribution_methods.create_actions(source, filename, sha1sum, size, target))
		actions.append(LogDistributionAction("Completed", filename, target))

		return actions

	def get_targets(self):
		return self.targets


class test(unittest.TestCase):
	def setUp(self):
		with open('test/local_machine_targets.json') as file:
			targets = json.load(file)
			self.targets = Targets(targets)

	def test(self):

		self.targets.create_distribution_actions('sourcedir/sourcefile', 'sourcefile', None, None, 'target2')

if __name__ == '__main__':
	unittest.main()
