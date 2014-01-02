
import logging
import json
import multiprocessing.pool
import os
import shutil
import threading
import time
import unittest
import weakref

import paramiko
import fabric.api
from fabric.api import local, run, settings
import fabric.network

from SendorTask import SendorAction, SendorActionContext

threadlocal = threading.local()

class FabricAction(SendorAction):

	def __init__(self, completion_weight):
		super(FabricAction, self).__init__(completion_weight)

	def fabric_local(self, command):
		with fabric.api.settings(warn_only=True):
			result = local(command, capture=True)

			if result.failed:
				raise Exception("Fabric command failed")
			return result

	def fabric_remote(self, command):
		with fabric.api.settings(warn_only=True):
			result = run(command)

			if result.failed:
				raise Exception("Fabric command failed")
			return result

class CopyFileAction(FabricAction):

	def __init__(self, source, sha1sum, size, target):
		super(CopyFileAction, self).__init__(completion_weight=50)
		self.source = source
		self.target = target

	def run(self, context):
		context.activity("Copying file")
		source = context.translate_path(self.source)
		target = context.translate_path(self.target)
		self.fabric_local('cp ' + source + ' ' + target)
		context.activity("Copy completed")

class TestIfFileUpToDateOnTargetAction(FabricAction):

	def __init__(self, filename, sha1sum, target):
		super(TestIfFileUpToDateOnTargetAction, self).__init__(completion_weight=10)
		self.filename = filename
		self.sha1sum = sha1sum
		self.target = target

	def run(self, context):

		context.activity("Connecting to SSH server")
		host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
		with settings(host_string=host_string, key_filename=self.target['private_key_file']):
			context.activity("Checking if remote file already is up-to-date")
			try:
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
			except:
				target_sha1sum = None

			if target_sha1sum == self.sha1sum:
				context.activity("Remote file is up-to-date; skipping transfer")
				context.file_up_to_date_on_target = True
			else:
				context.activity("Remote file is not up-to-date")
				context.file_up_to_date_on_target = False

class SftpSendFileAction(FabricAction):

	def __init__(self, source, filename, sha1sum, size, target):
		super(SftpSendFileAction, self).__init__(completion_weight=100)
		self.source = source
		self.filename = filename
		self.sha1sum = sha1sum
		self.target = target
		self.transferred = None

	def run(self, context):

		if not (hasattr(context, 'file_up_to_date_on_target') and context.file_up_to_date_on_target):
		
			def cb(transferred, total):
				self.transferred = transferred
				self.total = total
				ratio = float(self.transferred) / self.total
				context.completion_ratio(ratio)

			context.activity("Connecting to SSH server")
			host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
			with settings(host_string=host_string, key_filename=self.target['private_key_file']):
				source_path = context.translate_path(self.source)

				key_file = self.target['private_key_file']
				key = paramiko.RSAKey.from_private_key_file(key_file)
				transport = paramiko.Transport((self.target['host'], int(self.target['port'])))
				transport.connect(username = self.target['user'], pkey = key)
				context.activity("Transferring file via SFTP")
				sftp = paramiko.SFTPClient.from_transport(transport)
				sftp.put(source_path, self.filename, callback=cb)

				context.activity("Validating file integrity")
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
				if target_sha1sum != self.sha1sum:
					self.fabric_remote('rm ' + self.filename)
					context.activity("File corrupted during transfer; removed from target location")
					raise Exception("File corrupted during transfer")

			context.activity("Transfer complete")

class ParallelSftpSendFileAction(FabricAction):

	min_chunks = 1
	max_chunks = 99

	def __init__(self, source, filename, sha1sum, size, target):
		super(ParallelSftpSendFileAction, self).__init__(completion_weight=100)
		self.source = source
		self.filename = filename
		self.sha1sum = sha1sum
		self.size = size
		self.target = target
		self.transferred = None

	def run(self, context):

		if not (hasattr(context, 'file_up_to_date_on_target') and context.file_up_to_date_on_target):
			source = context.translate_path(self.source)
			max_parallel_transfers = int(self.target['max_parallel_transfers'])
			num_chunks = max(self.min_chunks, min(self.max_chunks, int(self.size / int(self.target['chunk_size']))))

			context.activity("Connecting to SSH server")
			host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
			with settings(host_string=host_string, key_filename=self.target['private_key_file']):

				context.activity("Creating file on target machine")
				self.fabric_remote('truncate -s ' + str(self.size) + ' ' + self.filename)

				context.activity("Transferring chunks using SFTP")

				completion_ratio_lock = threading.Lock()
				
				context.transmitted_size = 0
				context.total_size = self.size
				
				def transfer_file_thread_initializer(target):
					key_file = target['private_key_file']
					key = paramiko.RSAKey.from_private_key_file(key_file)
					transport = paramiko.Transport((target['host'], int(target['port'])))
					transport.connect(username = target['user'], pkey = key)
					threadlocal.sftp = paramiko.SFTPClient.from_transport(transport)
				
				def transfer_file_thread(context, sourcefile, targetfile, offset, length):
					with open(sourcefile, 'r') as inputfile:
						with threadlocal.sftp.file(targetfile, 'r+') as outputfile:
							inputfile.seek(offset, 0)
							outputfile.seek(offset, outputfile.SEEK_SET)
							bytes_transferred = 0

							while bytes_transferred < length:
								block_size = 16384
								if block_size > length - bytes_transferred:
									block_size = length - bytes_transferred
								data = inputfile.read(block_size)
								outputfile.write(data)
								bytes_transferred += block_size

								with completion_ratio_lock:
									context.transmitted_size += block_size
									ratio = float(context.transmitted_size) / context.total_size
									context.completion_ratio(ratio)

				# Bugfix for http://bugs.python.org/issue10015
				if not hasattr(threading.current_thread(), "_children"):
					threading.current_thread()._children = weakref.WeakKeyDictionary()

				thread_pool = multiprocessing.pool.ThreadPool(max_parallel_transfers, transfer_file_thread_initializer, (self.target, ))
					
				results = []
				for i in range(num_chunks):
					offset = (i * self.size) // num_chunks
					length = ((i + 1) * self.size) // num_chunks - offset
					results.append(thread_pool.apply_async(transfer_file_thread, (context, source, self.filename, offset, length)))

				thread_pool.close()

				# Wait for all chunks to complete transfer, and re-raise any exceptions thrown inside those worker threads
				for result in results:
					result.get()

				context.activity("Validating file integrity")
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
				if target_sha1sum != self.sha1sum:
					#self.fabric_remote('rm ' + self.filename)
					#context.activity("File corrupted during transfer; removed from target location")
					raise Exception("File corrupted during transfer")

			context.activity("Transfer complete")

class SendorActionTestContext(SendorActionContext):

	def activity(self, activity):
		logging.info("Activity: " + activity)

	def completion_ratio(self, completion_ratio):
		logging.info("Completion ratio: " + str(int(completion_ratio * 100)) + "%")

	def log(self, log):
		logging.info("Log: " + log)

class CopyFileActionUnitTest(unittest.TestCase):

	def setUp(self):
		os.mkdir('unittest')
		local('echo abc123 > unittest/source')

	def test_copy_file_action(self):
		self.assertFalse(os.path.exists('unittest/target'))
		action = CopyFileAction('unittest/source', None, None, 'unittest/target')
		action.run(SendorActionTestContext('unittest'))
		self.assertTrue(os.path.exists('unittest/target'))

	def tearDown(self):
		shutil.rmtree('unittest')

class SftpSendFileActionUnitTest(unittest.TestCase):

	root_path = 'unittest'
	upload_root = root_path + '/upload'
	file_name = 'testfile'
	source_path = upload_root + '/' + file_name
	file_contents = 'abc123'
	sha1sum = '61ee8b5601a84d5154387578466c8998848ba089'
	size = len(file_contents)

	def setUp(self):
		os.mkdir(self.root_path)
		os.mkdir(self.upload_root)
		local('echo ' + self.file_contents + ' > ' + self.upload_root + '/' + self.file_name)

	def test_sftp_send_file_action(self):

		targets = {}
		with open('test/ssh_localhost_targets.json') as file:
			targets = json.load(file)

		target = targets['ssh_localhost_target2']

		action = SftpSendFileAction(self.source_path, self.file_name, self.sha1sum, self.size, target)
		action.run(SendorActionTestContext('unittest'))

	def tearDown(self):
		shutil.rmtree(self.root_path)

class ParallelSftpSendFileActionUnitTest(unittest.TestCase):

	root_path = 'unittest'
	upload_root = root_path + '/upload'
	temp_path = root_path + '/temp'
	file_name = 'testfile'
	source_path = upload_root + '/' + file_name
	file_contents = 'abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890abcdefghijklmnopq1234567890'
	sha1sum = '67b3642bc208372ead45399884da28c360fc6d36'
	size = len(file_contents) + 1 # add 1 byte since the 'echo' command will append a \r to the file's contents
	
	def setUp(self):
		os.mkdir(self.root_path)
		os.mkdir(self.upload_root)
		os.mkdir(self.temp_path)
		local('echo ' + self.file_contents + ' > ' + self.upload_root + '/' + self.file_name)

	def test_parallel_sftp_send_file_action(self):

		targets = {}
		with open('test/ssh_localhost_targets.json') as file:
			targets = json.load(file)

		target = targets['ssh_localhost_target3']

		action = ParallelSftpSendFileAction(self.source_path, self.file_name, self.sha1sum, self.size, target)
		action.run(SendorActionTestContext(self.temp_path))

	def tearDown(self):
		shutil.rmtree(self.root_path)

if __name__ == '__main__':
	logging.basicConfig(level=logging.ERROR)
	unittest.main()
	fabric.network.disconnect_all()
