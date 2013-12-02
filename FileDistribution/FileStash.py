
import datetime
import dateutil
import dateutil.parser
import json
import os
import os.path
import shutil
import thread
import threading
import time
import unittest

from fabric.api import local

from Observable import Observable

class RefCount(object):

	def __init__(self):
		self.reference_count = 0

	def add_ref(self):
		self.reference_count += 1
		return self.reference_count

	def rem_ref(self):
		self.reference_count -= 1
		return self.reference_count
		
	def ref_count(self):
		return self.reference_count

class PhysicalFile(RefCount):

	def __init__(self, sha1sum):
		super(PhysicalFile, self).__init__()
		self.sha1sum = sha1sum

		if len(sha1sum) != 40:
			raise Exception(sha1sum + " is not a valid SHA1 hash value")

class StashedFile(RefCount):

	def __init__(self, file_id, root_path, filename, physical_file, timestamp, size):
		super(StashedFile, self).__init__()
		self.file_id = file_id
		self.root_path = root_path
		self.full_path_filename = os.path.join(root_path, physical_file.sha1sum)
		self.original_filename = filename
		self.physical_file = physical_file
		self.timestamp = timestamp
		self.size = size

	def to_json(self):
		return { 'file_id' : self.file_id,
			'original_filename' : self.original_filename,
			'sha1sum' : self.physical_file.sha1sum,
			'timestamp' : str(self.timestamp),
			'size' : str(self.size),
			'is_deletable' : self.ref_count() == 0 }

def remove_old_files_thread(file_stash, check_interval_seconds, max_age_ays):

	while True:
		time.sleep(check_interval_seconds)
		files = file_stash.list()
		now = datetime.datetime.utcnow()
		max_timedelta = datetime.timedelta(days=max_age_days)
		for file in files:
			age = now - file.timestamp
			if age > max_timedelta:
				try:
					stashed_file = file_stash.remove(file.file_id)
				except:
					pass

class FileStash(Observable):

	class FileDoesNotExistError(Exception):
		pass

	class FileCannotBeRemovedError(Exception):
		pass

	index_filename = 'index.json'

	def __init__(self, root_path, file_max_days):
		super(FileStash, self).__init__()
		if not os.path.exists(root_path):
			raise Exception("Stash directory " + root_path + " does not exist")

		self.index_lock = threading.RLock()
		self.root_path = root_path
		self.unique_id = 0
		self.build_index()
		
		if file_max_days:
			thread.start_new_thread(remove_old_files_thread, (self, 3600, file_max_days))
		
	def save_index(self):
		with self.index_lock:
			filename = os.path.join(self.root_path, self.index_filename)
			with open(filename, 'w') as index_file:
				json.dump(self.stashed_files, index_file, default = lambda file: file.to_json())
			
	def build_index(self):
		""" Create an index for all the files in the stash directory tree """

		with self.index_lock:
		
			# Load index file
			old_index_filename = os.path.join(self.root_path, self.index_filename)
			old_index = {}
			try:
				with open(old_index_filename) as old_index_file:
					old_index = json.load(old_index_file)
			except IOError as e:
				pass

			# Locate all on-disk files in file stash directory; remove directories
			on_disk_files = {}
			for root, dirs, filenames in os.walk(self.root_path):

				for dir in dirs:
					shutil.rmtree(os.path.join(root, dir))
			
				for filename in filenames:
					if filename != self.index_filename:
						on_disk_files[filename] = True;

			# Remove index entries if the corresponding file is missing on-disk
			for id, entry in old_index.items():
				if not entry['sha1sum'] in on_disk_files:
					del old_index[id]

			# Remove files which are not referenced by any index entry
			referenced_files = {}
			for entry in old_index.values():
				referenced_files[entry['sha1sum']] = True
				
			for file in on_disk_files.keys():
				if not file in referenced_files:
					os.remove(os.path.join(self.root_path, file))
					
			# Add all remaining index entries to stash
			self.physical_files = {}
			self.stashed_files = {}
			for file in old_index.values():
				self.add_to_index(file['original_filename'], file['sha1sum'], dateutil.parser.parse(file['timestamp']), int(file['size']))
				
			
		self.save_index()

	def add_to_index(self, filename, sha1sum, timestamp, size):
		""" Add a new file to the index
			The file should be present in the stash directory tree
			"""

		def add_physical_file(self, sha1sum):
			if not sha1sum in self.physical_files:
				self.physical_files[sha1sum] = PhysicalFile(sha1sum)

			self.physical_files[sha1sum].add_ref()
			return self.physical_files[sha1sum]

		def add_stashed_file(self, filename, physical_file, timestamp, size):
			id = str(self.unique_id)
			stashed_file = StashedFile(id, self.root_path, filename, physical_file, timestamp, size)
			self.stashed_files[id] = stashed_file
			self.unique_id += 1
			return self.stashed_files[id]

		physical_file = add_physical_file(self, sha1sum)
		stashed_file = add_stashed_file(self, filename, physical_file, timestamp, size)

		self.notify(event_type='add', stashed_file=stashed_file)
		return stashed_file

	def remove_from_index(self, id):
		""" Remove a file from the index
			The file will not be removed from the stash directory tree
			"""
		
		def remove_stashed_file(self, id):
			del self.stashed_files[id]
			
		def deref_physical_file(self, physical_file):
			return physical_file.rem_ref()

		stashed_file = self.stashed_files.get(id)
		if not stashed_file:
			raise Exception("File not in stash")
		else:
			physical_file = stashed_file.physical_file
			remove_stashed_file(self, id)
			self.notify(event_type='remove', stashed_file=stashed_file)
			return deref_physical_file(self, physical_file) == 0

	def add(self, original_path, filename, timestamp):
		""" Add a file to the stash
			If the file does not yet exist in the stash directory tree, the file will be moved
			from its original location to the stash
			Otherwise, the file is simply deleted from its original location
			"""
			
		with self.index_lock:
			original_file = os.path.join(original_path, filename)

			sha1sum = local('sha1sum -b ' + original_file, capture = True)[:40]
			size = os.stat(original_file).st_size

			file = self.add_to_index(filename, sha1sum, timestamp, size)

			if os.path.exists(file.full_path_filename):
				os.remove(original_file)
			else:
				shutil.move(original_file, file.full_path_filename)

			self.save_index()
			return file

	def remove(self, id):
		""" Remove a file from the stash
			The file should exist in the index and stash directory tree
			If this is the last reference to the on-disk file, the on-disk file will be removed
			"""

		with self.index_lock:
			file = self.get(id)
			if not file:
				raise FileStash.FileDoesNotExistError("File with id " + str(id) + " does not exist in file stash")
			full_path_filename = file.full_path_filename
			if file.ref_count() != 0:
				raise FileStash.FileCannotBeRemovedError("File with id " + str(id) + " has nonzero refcount and cannot be removed")
			else:
				if self.remove_from_index(id):
					os.remove(full_path_filename)
				
			self.save_index()

	def remove_all_unlocked_files(self):
		with self.index_lock:
			ids = self.stashed_files.keys()[:]
			for id in ids:
				try:
					self.remove(id)
				except:
					pass
	
	def list(self):
		with self.index_lock:
			return self.stashed_files.values()[:]
	
	def get(self, id):
		""" Locate the index entry for a file, or return None if it does not exist """
		with self.index_lock:
			return self.stashed_files.get(id)

	def lock(self, id):
		""" Protect a stashed file from deletion """
		with self.index_lock:
			stashed_file = self.get(id)
			if not stashed_file:
				raise FileStash.FileDoesNotExistError("File with id " + str(id) + " does not exist in file stash")
			else:
				stashed_file.add_ref()
				self.notify(event_type='change', stashed_file=stashed_file)
				return stashed_file

	def unlock(self, stashed_file):
		""" Unprotect a stashed file from deletion
			The marking is done using reference counts, so a file will only become deletable
			when all lock() calls on it have been matched with unlock() calls """
		with self.index_lock:
			stashed_file.rem_ref()
			self.notify(event_type='change', stashed_file=stashed_file)
	

class StashedFileUnitTest(unittest.TestCase):

	def test_file(self):

		self.assertRaises(Exception, StashedFile, 1, "root/path", "myfilename", "invalid_hash")

		physical_file = PhysicalFile("cf53e64d1bb75ce5a4e71324777d7ed6cc19c435")
		stashed_file = StashedFile(1, "root/path", "myfilename", physical_file, datetime.datetime.utcnow(), 1234)
		self.assertEquals(stashed_file.full_path_filename, "root/path/cf53e64d1bb75ce5a4e71324777d7ed6cc19c435")

class FileStashUnitTest(unittest.TestCase):

	# File 1 & 4 have the same name
	# File 3 & 5 & 6 have the same SHA1 hash
	# File 5 & 6 are identical

	file1_name = 'hello1.txt'
	file1_sha1sum = 'a2abbbf0d432a8097fd7a4d421cc91881309cda2'
	file2_name = 'hello2.txt'
	file2_sha1sum = 'dca028d53b41169f839eeefe489b02e0aa7b5d27'
	file3_name = 'hello3.txt'
	file3_sha1sum = 'ca44a076d1ac49f10ebb55949a9a16805af69bcd'
	file4_name = 'hello1.txt'
	file4_sha1sum = '77b8b233f03f1720c0642f6e1ce395fbfe0322ed'
	file5_name = 'hello5.txt'
	file5_sha1sum = 'ca44a076d1ac49f10ebb55949a9a16805af69bcd'
	file6_name = 'hello5.txt'
	file6_sha1sum = 'ca44a076d1ac49f10ebb55949a9a16805af69bcd'

	def setUp(self):

		# Construct a file-stash
		os.mkdir('unittest')
		os.mkdir('unittest/file_stash')

	def test(self):

		def notification(event_type, stashed_file):
			print event_type + " " + str(stashed_file.file_id)

		# Add two files to initial stash
		file_stash_init = FileStash('unittest/file_stash', None)
		local('echo "Hello World 1" > unittest/' + self.file1_name)
		local('echo "Hello World 2" > unittest/' + self.file2_name)
		file_stash_init.add('unittest', self.file1_name, datetime.datetime.utcnow())
		file_stash_init.add('unittest', self.file2_name, datetime.datetime.utcnow())
		# Initial stash will no longer be used from now on
		
		# Create main stash
		file_stash = FileStash('unittest/file_stash', None)
		file_stash.subscribe(notification)
		# file1 and file2 should already exist in the file stash
		self.assertEquals(len(file_stash.stashed_files), 2)

		# Files not in the stash should not yield any hits
		self.assertEquals(file_stash.get(12345678), None)

		# file4 has the same filename as file1 but different content
		# file3 and file5 have different names but identical content
		# file5 and file6 are identical

		# Create temporary files outside of the stash, and add them
		local('echo "Hello World 3" > unittest/' + self.file3_name)
		file3 = file_stash.add('unittest', self.file3_name, datetime.datetime.utcnow())
		local('echo "Hello World 4" > unittest/' + self.file4_name)
		file4 = file_stash.add('unittest', self.file4_name, datetime.datetime.utcnow())
		local('echo "Hello World 3" > unittest/' + self.file5_name)
		file5 = file_stash.add('unittest', self.file5_name, datetime.datetime.utcnow())
		local('echo "Hello World 3" > unittest/' + self.file6_name)
		file6 = file_stash.add('unittest', self.file6_name, datetime.datetime.utcnow())

		file3_id = file3.file_id
		file4_id = file4.file_id
		file5_id = file5.file_id
		file6_id = file6.file_id

		# Validate that identical files result in separate stashed file IDs
		self.assertNotEquals(file5_id, file6_id)
		
		# Validate that all files have been added to the stash
#		self.assertNotEquals(file_stash.get(file1_id), None)
#		self.assertNotEquals(file_stash.get(file2_id), None)
		self.assertNotEquals(file_stash.get(file3_id), None)
		self.assertNotEquals(file_stash.get(file4_id), None)
		self.assertNotEquals(file_stash.get(file5_id), None)
		self.assertNotEquals(file_stash.get(file6_id), None)

		# Remove two files with identical content
		file_stash.remove(file3_id)
		self.assertEquals(file_stash.get(file3_id), None)
		self.assertNotEquals(file_stash.get(file5_id), None)
		file_stash.remove(file5_id)
		self.assertEquals(file_stash.get(file3_id), None)
		self.assertEquals(file_stash.get(file5_id), None)

		# Ensure that it is not possible to remove locked files
		file_stash.lock(file4_id)
		self.assertRaises(FileStash.FileCannotBeRemovedError, file_stash.remove, file4_id)
		file_stash.unlock(file4)

		# Removing a nonexistent file should result in an error
		self.assertRaises(FileStash.FileDoesNotExistError, file_stash.remove, 12345678)
		
		# Remove one file which has identical name to another file 
		file_stash.remove(file4_id)
		self.assertEquals(file_stash.get(file4_id), None)

		# Remove one file which has identical name and contents to another file 
		file_stash.remove(file6_id)
		self.assertEquals(file_stash.get(file6_id), None)

		# At this point, only the first two files should remain in the stash
		self.assertEquals(len(file_stash.stashed_files), 2)

		# Remove all files from stash
		file_stash.remove_all_unlocked_files()
		self.assertEquals(len(file_stash.stashed_files), 0)

	def tearDown(self):
		shutil.rmtree('unittest')

if __name__ == '__main__':
	unittest.main()
