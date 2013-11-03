
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

from SendorJob import SendorTask, SendorAction, SendorActionContext

threadlocal = threading.local()

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

	def __init__(self, source, sha1sum, size, target):
		super(CopyFileAction, self).__init__()
		self.source = source
		self.target = target

	def run(self, context):
		context.progress("Copying file")
		source = context.translate_path(self.source)
		target = context.translate_path(self.target)
		self.fabric_local('cp ' + source + ' ' + target)
		context.progress("Copy completed")

class SftpSendFileAction(FabricAction):

	def __init__(self, source, filename, sha1sum, size, target):
		super(SftpSendFileAction, self).__init__()
		self.source = source
		self.filename = filename
		self.sha1sum = sha1sum
		self.target = target
		self.transferred = None

	def run(self, context):

		def cb(transferred, total):
			self.transferred = transferred
			self.total = total

		context.progress("Connecting to SSH server")
		host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
		with settings(host_string=host_string, key_filename=self.target['private_key_file']):
			context.progress("Checking if remote file already is up-to-date")
			try:
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
			except:
				target_sha1sum = None
				
			if target_sha1sum == self.sha1sum:
				context.progress("Remote file is up-to-date; skipping transfer")
			else:

				context.progress("Connecting to SSH server")
				source_path = context.translate_path(self.source)

				key_file = self.target['private_key_file']
				key = paramiko.RSAKey.from_private_key_file(key_file)
				transport = paramiko.Transport((self.target['host'], int(self.target['port'])))
				transport.connect(username = self.target['user'], pkey = key)
				context.progress("Transferring file via SFTP")
				sftp = paramiko.SFTPClient.from_transport(transport)
				sftp.put(source_path, self.filename, callback=cb)

				context.progress("Validating file integrity")
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
				if target_sha1sum != self.sha1sum:
					self.fabric_remote('rm ' + self.filename)
					context.progress("File corrupted during transfer; removed from target location")
					raise Exception("File corrupted during transfer")

		context.progress("Transfer complete")

class ParallelSftpSendFileAction(FabricAction):

	min_chunks = 1
	max_chunks = 99

	def __init__(self, source, filename, sha1sum, size, target):
		super(ParallelSftpSendFileAction, self).__init__()
		self.source = source
		self.filename = filename
		self.sha1sum = sha1sum
		self.size = size
		self.target = target
		self.transferred = None

	def run(self, context):

		source = context.translate_path(self.source)
		max_parallel_transfers = int(self.target['max_parallel_transfers'])
		num_chunks = max(self.min_chunks, min(self.max_chunks, int(self.size / int(self.target['chunk_size']))))
		temp_directory = context.work_directory
		temp_filename_prefix = 'chunk_'
		temp_file_prefix = os.path.join(temp_directory, temp_filename_prefix)

		context.progress("Connecting to SSH server")
		host_string = self.target['user'] + '@' + self.target['host'] + ':' + self.target['port']
		with settings(host_string=host_string, key_filename=self.target['private_key_file']):
			context.progress("Checking if remote file already is up-to-date")
			try:
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
			except:
				target_sha1sum = None

			if target_sha1sum == self.sha1sum:
				context.progress("Remote file is up-to-date; skipping transfer")
			else:
		
				context.progress("Splitting original file into chunks")
				self.fabric_local('split -d -n ' + str(num_chunks) + ' ' + source + ' ' + temp_file_prefix)
				
				context.progress("Transferring chunks using SFTP")

				progress_lock = threading.Lock()
				
				context.completed_chunks = 0
				context.total_chunks = num_chunks
				
				def transfer_file_thread_initializer(target):
					key_file = target['private_key_file']
					key = paramiko.RSAKey.from_private_key_file(key_file)
					transport = paramiko.Transport((target['host'], int(target['port'])))
					transport.connect(username = target['user'], pkey = key)
					threadlocal.sftp = paramiko.SFTPClient.from_transport(transport)
				
				def transfer_file_thread(context, tempfile, targetfile, target):
					threadlocal.sftp.put(tempfile, targetfile, callback=None)
					with progress_lock:
						context.completed_chunks += 1
						ratio = int(100 * context.completed_chunks / context.total_chunks)
						context.progress("Transferring chunks using SFTP - " + str(ratio) + "% done")

				# Bugfix for http://bugs.python.org/issue10015
				if not hasattr(threading.current_thread(), "_children"):
					threading.current_thread()._children = weakref.WeakKeyDictionary()

				thread_pool = multiprocessing.pool.ThreadPool(max_parallel_transfers, transfer_file_thread_initializer, (self.target, ))
					
				results = []
				for i in range(num_chunks):
					temp_filename_suffix = u'%02d' % i
					tempfile = temp_file_prefix + temp_filename_suffix
					targetfile = temp_filename_prefix + temp_filename_suffix
					results.append(thread_pool.apply_async(transfer_file_thread, (context, tempfile, targetfile, self.target)))

				thread_pool.close()

				# Wait for all chunks to complete transfer, and re-raise any exceptions thrown inside those worker threads
				for result in results:
					result.get()

				context.progress("Merging chunks to a single file")
				self.fabric_remote('cat ' + temp_filename_prefix + '?? > ' + self.filename)
				context.progress("Removing chunks")
				self.fabric_remote('rm ' + temp_filename_prefix + '??')
				context.progress("Validating file integrity")
				target_sha1sum = self.fabric_remote('sha1sum -b ' + self.filename)[:40]
				if target_sha1sum != self.sha1sum:
					self.fabric_remote('rm ' + self.filename)
					context.progress("File corrupted during transfer; removed from target location")
					raise Exception("File corrupted during transfer")

		context.progress("Transfer complete")

class SendorActionTestContext(SendorActionContext):

	def progress(self, message):
		logging.info("Progress: " + message)

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
	size = len(file_contents)
	
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
