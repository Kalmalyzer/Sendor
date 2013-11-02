
import json
import logging
import os
import unittest

from SendorJob import SendorTask, SendorAction
from FileStash import StashedFile, PhysicalFile

import target_distribution_methods

import target_distribution_method_cp
import target_distribution_method_scp
import target_distribution_method_sftp
import target_distribution_method_parallel_scp
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

	def create_distribution_actions(self, source, id):
		if not id in self.targets:
			raise Exception("id " + id + " does not exist in targets")

		target = self.targets[id]
		actions = [ LogDistributionAction("Started", source.original_filename, target),
			target_distribution_methods.create_action(source, target),
			LogDistributionAction("Completed", source.original_filename, target) ]

		return actions

	def get_targets(self):
		return self.targets


class test(unittest.TestCase):

	source_file_path = 'sourcedir'
	source_file_name = 'testfile'
	source_file_contents = 'abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890'
	source_file_sha1sum = '67b3642bc208372ead45399884da28c360fc6d36'
	source_file_timestamp = '0'
	source_file_size = 108
	physical_file = PhysicalFile(source_file_sha1sum)
	source_file = StashedFile(None, source_file_path, source_file_name, physical_file, source_file_timestamp, source_file_size)

	target = 'target2'
	
	def setUp(self):
		with open('test/local_machine_targets.json') as file:
			targets = json.load(file)
			self.targets = Targets(targets)

	def test(self):

		self.targets.create_distribution_actions(self.source_file, self.target)

if __name__ == '__main__':
	unittest.main()
