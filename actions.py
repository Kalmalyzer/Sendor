
import logging
import json
import os
import shutil
import threading
import time
import unittest

import paramiko
import fabric.api
from fabric.api import local, run, settings
import fabric.network

from SendorJob import SendorTask, SendorAction, SendorActionContext
from FileStash import StashedFile, PhysicalFile


class FabricAction(SendorAction):

	def __init__(self):
		super(FabricAction, self).__init__()

	def fabric_local(self, command):
		with fabric.api.settings(warn_only=True):
			result = local(command, capture=True)

			logger = logging.getLogger('fabric')
			logger.info(command)
			logger.info(result)
			logger.info(result.stderr)

			if result.failed:
				raise Exception("Fabric command failed")
			return result

	def fabric_remote(self, command):
		with fabric.api.settings(warn_only=True):
			result = run(command)

			logger = logging.getLogger('fabric')
			logger.info(command)
			logger.info(result)
			logger.info(result.stderr)

			if result.failed:
				raise Exception("Fabric command failed")
			return result

class CopyFileAction(FabricAction):

	def __init__(self, source, target):
		super(CopyFileAction, self).__init__()
		self.source = source
		self.target = target

	def run(self, context):
		context.progress("Copying file")
		source = context.translate_path(self.source.full_path_filename)
		target = context.translate_path(self.target)
		self.fabric_local('cp ' + source + ' ' + target)
		context.progress("Copy completed")

class ScpSendFileAction(FabricAction):

	def __init__(self, source, target):
		super(ScpSendFileAction, self).__init__()
		self.source = source
		self.target = target

	def run(self, context):
		context.progress("Transferring file using SCP")
		source_path = context.translate_path(self.source.full_path_filename)
		target_path = self.target['user'] + '@' + self.target['host'] + ":" + self.source.original_filename
		target_port = self.target['port']
		key_file = self.target['private_key_file']
		self.fabric_local('scp ' + ' -B -P ' + target_port + ' -i ' + key_file + ' ' + source_path + ' ' + target_path)
		context.progress("Transfer completed")

class SftpSendFileAction(FabricAction):

	def __init__(self, source, target):
		super(SftpSendFileAction, self).__init__()
		self.source = source
		self.target = target
		self.transferred = None

	def run(self, context):

		def cb(transferred, total):
			self.transferred = transferred
			self.total = total

		context.progress("Connecting to SSH server")
		source_path = context.translate_path(self.source.full_path_filename)

		key_file = self.target['private_key_file']
		key = paramiko.RSAKey.from_private_key_file(key_file)
		transport = paramiko.Transport((self.target['host'], int(self.target['port'])))
		transport.connect(username = self.target['user'], pkey = key)
		context.progress("Transferring file via SFTP")
		sftp = paramiko.SFTPClient.from_transport(transport)
		sftp.put(source_path, self.source.original_filename, callback=cb)

		context.progress("Connecting to SSH server again")
		host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
		with settings(host_string=host_string, key_filename=self.target['private_key_file']):
			context.progress("Validating file integrity")
			target_sha1sum = self.fabric_remote('sha1sum -b ' + self.source.original_filename)[:40]
			if target_sha1sum != self.source.physical_file.sha1sum:
				self.fabric_remote('rm ' + self.source.original_filename)
				context.progress("File corrupted during transfer; removed from target location")
				raise Exception("File corrupted during transfer")

		context.progress("Transfer complete")

class ParallelScpSendFileAction(FabricAction):

	def __init__(self, source, target):
		super(ParallelScpSendFileAction, self).__init__()
		self.source = source
		self.target = target
		self.transferred = None

	def run(self, context):

		source = context.translate_path(self.source.full_path_filename)
		num_parallel_transfers = int(self.target['max_parallel_transfers'])
		temp_directory = context.work_directory
		temp_filename_prefix = 'chunk_'
		temp_file_prefix = os.path.join(temp_directory, temp_filename_prefix)

		context.progress("Splitting original file into chunks")
		self.fabric_local('split -d -n ' + str(num_parallel_transfers) + ' ' + source + ' ' + temp_file_prefix)

		context.progress("Transferring chunks using SCP")
		
		def transfer_file_thread(self, tempfile, targetfile, target):
			source_path = tempfile
			target_path = self.target['user'] + '@' + self.target['host'] + ":" + targetfile
			target_port = self.target['port']
			key_file = self.target['private_key_file']
			self.fabric_local('scp ' + ' -B -P ' + target_port + ' -i ' + key_file + ' ' + source_path + ' ' + target_path)
				
		threads = []
			
		for i in range(num_parallel_transfers):
			temp_filename_suffix = u'%02d' % i
			tempfile = temp_file_prefix + temp_filename_suffix
			targetfile = temp_filename_prefix + temp_filename_suffix
			thread = threading.Thread(target=transfer_file_thread, args=(self, tempfile, targetfile, self.target))
			thread.start()
			threads.append(thread)

		for thread in threads:
			thread.join()

		context.progress("Connecting to host via SSH")
		host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
		with settings(host_string=host_string, key_filename=self.target['private_key_file']):
			context.progress("Merging chunks to a single file")
			self.fabric_remote('cat ' + temp_filename_prefix + '?? > ' + self.source.original_filename)
			context.progress("Removing chunks")
			self.fabric_remote('rm ' + temp_filename_prefix + '??')

		context.progress("Transfer complete")

class ParallelSftpSendFileAction(FabricAction):

	def __init__(self, source, target):
		super(ParallelSftpSendFileAction, self).__init__()
		self.source = source
		self.target = target
		self.transferred = None

	def run(self, context):

		source = context.translate_path(self.source.full_path_filename)
		num_parallel_transfers = int(self.target['max_parallel_transfers'])
		temp_directory = context.work_directory
		temp_filename_prefix = 'chunk_'
		temp_file_prefix = os.path.join(temp_directory, temp_filename_prefix)
		
		context.progress("Splitting original file into chunks")
		self.fabric_local('split -d -n ' + str(num_parallel_transfers) + ' ' + source + ' ' + temp_file_prefix)
		
		context.progress("Transferring chunks using SFTP")
		def transfer_file_thread(tempfile, targetfile, target):
			key_file = target['private_key_file']
			key = paramiko.RSAKey.from_private_key_file(key_file)
			transport = paramiko.Transport((target['host'], int(target['port'])))
			transport.connect(username = target['user'], pkey = key)
			sftp = paramiko.SFTPClient.from_transport(transport)
			sftp.put(tempfile, targetfile, callback=None)
				
		threads = []
			
		for i in range(num_parallel_transfers):
			temp_filename_suffix = u'%02d' % i
			tempfile = temp_file_prefix + temp_filename_suffix
			targetfile = temp_filename_prefix + temp_filename_suffix
			thread = threading.Thread(target=transfer_file_thread, args=(tempfile, targetfile, self.target))
			thread.start()
			threads.append(thread)

		for thread in threads:
			thread.join()

		context.progress("Connecting to host via SSH")
		host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
		with settings(host_string=host_string, key_filename=self.target['private_key_file']):
			context.progress("Merging chunks to a single file")
			self.fabric_remote('cat ' + temp_filename_prefix + '?? > ' + self.source.original_filename)
			context.progress("Removing chunks")
			self.fabric_remote('rm ' + temp_filename_prefix + '??')
			context.progress("Validating file integrity")
			target_sha1sum = self.fabric_remote('sha1sum -b ' + self.source.original_filename)[:40]
			if target_sha1sum != self.source.physical_file.sha1sum:
				self.fabric_remote('rm ' + self.source.original_filename)
				context.progress("File corrupted during transfer; removed from target location")
				raise Exception("File corrupted during transfer")

		context.progress("Transfer complete")

class SendorActionTestContext(SendorActionContext):

	def progress(self, message):
		logging.info("Progress: " + message)

class CopyFileActionUnitTest(unittest.TestCase):

	root_path = 'unittest'
	temp_path = root_path
	upload_root = root_path + '/upload'
	source_file_name = 'source'
	source_file_contents = 'abc123'
	source_file_sha1sum = '61ee8b5601a84d5154387578466c8998848ba089'
	source_file_timestamp = '0'
	source_file_size = 6
	physical_file = PhysicalFile(source_file_sha1sum)
	source_file = StashedFile(None, upload_root, source_file_name, physical_file, source_file_timestamp, source_file_size)

	target_file_fullpath = root_path + '/target'

	def setUp(self):
		os.mkdir(self.root_path)
		os.mkdir(self.upload_root)
		local('echo ' + self.source_file_contents + ' > ' + self.upload_root + '/' + self.source_file_sha1sum)

	def test_copy_file_action(self):
		self.assertFalse(os.path.exists(self.target_file_fullpath))
		action = CopyFileAction(self.source_file, self.target_file_fullpath)
		action.run(SendorActionTestContext(self.temp_path))
		self.assertTrue(os.path.exists(self.target_file_fullpath))

	def tearDown(self):
		shutil.rmtree(self.root_path)

class SftpSendFileActionUnitTest(unittest.TestCase):

	root_path = 'unittest'
	temp_path = root_path
	upload_root = root_path + '/upload'
	source_file_name = 'testfile'
	source_file_contents = 'abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890'
	source_file_sha1sum = '67b3642bc208372ead45399884da28c360fc6d36'
	source_file_timestamp = '0'
	source_file_size = 108
	physical_file = PhysicalFile(source_file_sha1sum)
	source_file = StashedFile(None, upload_root, source_file_name, physical_file, source_file_timestamp, source_file_size)

	def setUp(self):
		os.mkdir(self.root_path)
		os.mkdir(self.upload_root)
		local('echo ' + self.source_file_contents + ' > ' + self.upload_root + '/' + self.source_file_sha1sum)

	def test_sftp_send_file_action(self):

		targets = {}
		with open('test/ssh_localhost_targets.json') as file:
			targets = json.load(file)

		target = targets['ssh_localhost_target2']

		action = SftpSendFileAction(self.source_file, target)
		action.run(SendorActionTestContext(self.temp_path))

	def tearDown(self):
		shutil.rmtree(self.root_path)

class ParallelSftpSendFileActionUnitTest(unittest.TestCase):

	root_path = 'unittest'
	temp_path = root_path + '/temp'
	upload_root = root_path + '/upload'
	source_file_name = 'testfile'
	source_file_contents = 'abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890'
	source_file_sha1sum = '67b3642bc208372ead45399884da28c360fc6d36'
	source_file_timestamp = '0'
	source_file_size = 108
	physical_file = PhysicalFile(source_file_sha1sum)
	source_file = StashedFile(None, upload_root, source_file_name, physical_file, source_file_timestamp, source_file_size)

	def setUp(self):
		os.mkdir(self.root_path)
		os.mkdir(self.upload_root)
		os.mkdir(self.temp_path)
		local('echo ' + self.source_file_contents + ' > ' + self.upload_root + '/' + self.source_file_sha1sum)

	def test_parallel_sftp_send_file_action(self):

		targets = {}
		with open('test/ssh_localhost_targets.json') as file:
			targets = json.load(file)

		target = targets['ssh_localhost_target3']

		action = ParallelSftpSendFileAction(self.source_file, target)
		action.run(SendorActionTestContext(self.temp_path))

	def tearDown(self):
		shutil.rmtree(self.root_path)

if __name__ == '__main__':
	logging.basicConfig(level=logging.ERROR)
	unittest.main()
	fabric.network.disconnect_all()
