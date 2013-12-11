
import json
import logging
import os
import shutil
import unittest

from flask import Flask, Blueprint, Response, jsonify

from SendorTask import SendorTask

from SendorQueue import SendorQueue
from Targets import Targets
from FileStash import FileStash

logger = logging.getLogger('main.api')

class DistributeFileTask(SendorTask):

	def __init__(self, file_stash, source, target, stashed_file_id):
		super(DistributeFileTask, self).__init__()
		self.file_stash = file_stash
		self.source = source
		self.target = target
		self.stashed_file = self.file_stash.lock(stashed_file_id)

	def string_description(self):
		return "Distribute file " + self.source + " to " + self.target

	def completed(self):
		super(DistributeFileTask, self).completed()
		self.file_stash.unlock(self.stashed_file)

	def failed(self):
		super(DistributeFileTask, self).failed()
		self.file_stash.unlock(self.stashed_file)
	
	def canceled(self):
		super(DistributeFileTask, self).canceled()
		self.file_stash.unlock(self.stashed_file)

def create_rest_api(sendor_queue, targets, file_stash):

	api_app = Blueprint('api', __name__)

	@api_app.route('/tasks', methods = ['GET'])
	def tasks_get():
		tasks = sendor_queue.list()
		tasks_progress = [task.progress() for task in tasks]
		return jsonify(collection=tasks_progress)

	@api_app.route('/tasks/<int:task_id>', methods = ['GET'])
	def task_get(task_id):
		try:
			task = sendor_queue.get(task_id)
			task_progress = task.progress()
			return jsonify(collection=task_progress)
		except SendorQueue.TaskNotFoundError, e:
			response = jsonify({'message' : e.message})
			response.status_code = 404
			return response
		except Exception, e:
			print e.message

	@api_app.route('/tasks/<int:task_id>/cancel', methods = ['PUT'])
	def task_cancel(task_id):
		try:
			task = sendor_queue.get(task_id)
			sendor_queue.cancel(task)
			return jsonify({})
		except SendorQueue.TaskNotFoundError, e:
			response = jsonify({'message' : e.message})
			response.status_code = 404
			return response
		except SendorQueue.TaskHasCompletedError, e:
			response = jsonify({'message' : e.message})
			response.status_code = 403
			return response

	@api_app.route('/targets', methods = ['GET'])
	def targets_get():
		target_list = targets.get_targets()
		targets_contents = [{ 'target_id' : target_id, 'name' : target_details['name'] } for (target_id, target_details) in target_list.iteritems()]
		return jsonify(collection=targets_contents)

	@api_app.route('/file_stash', methods = ['GET'])
	def file_stash_get():
		sorted_file_stash = sorted(file_stash.list(), cmp = lambda x, y: cmp(x.timestamp, y.timestamp))
		file_stash_contents = [file.to_json() for file in sorted_file_stash]
		return jsonify(collection=file_stash_contents)

	@api_app.route('/file_stash/<file_id>', methods = ['DELETE'])
	def file_stash_delete(file_id):
		try:
			file_stash.remove(file_id)
			return jsonify({})
		except FileStash.FileDoesNotExistError, e:
			response = jsonify({'message' : e.message})
			response.status_code = 404
			return response
		except FileStash.FileCannotBeRemovedError, e:
			response = jsonify({'message' : e.message})
			response.status_code = 403
			return response
	
	@api_app.route('/file_stash/<file_id>/distribute/<target_id>', methods = ['POST'])
	def file_stash_distribute(file_id, target_id):
		try:
			stashed_file = file_stash.lock(file_id)
		except FileStash.FileDoesNotExistError, e:
			response = jsonify({'message' : e.message})
			response.status_code = 404
			return response

		try:
			distribute_file_task = DistributeFileTask(file_stash, stashed_file.original_filename, target_id, file_id)
			distribute_file_actions = targets.create_distribution_actions(stashed_file.full_path_filename, stashed_file.original_filename, stashed_file.physical_file.sha1sum, stashed_file.size, target_id)
			distribute_file_task.actions.extend(distribute_file_actions)
			sendor_queue.add(distribute_file_task)
		except:
			file_stash.unlock(stashed_file)
			raise

		file_stash.unlock(stashed_file)
		return jsonify({})

	return api_app

class ApiTestCase(unittest.TestCase):

	work_directory = 'unittest'

	def setUp(self):
	
		os.mkdir(self.work_directory)

		self.sendor_queue = SendorQueue(num_processes=4, work_directory=self.work_directory, max_task_execution_time=10, max_task_finalization_time=1, task_cleanup_interval_seconds=None, max_task_wait_seconds=None, max_task_exist_days=None)
		with open('test/local_machine_targets.json') as file:
			targets = json.load(file)
			self.targets = Targets(targets)

		os.mkdir('unittest/file_stash')
		self.file_stash = FileStash('unittest/file_stash', None)
		
		root = Flask(__name__)
		root.register_blueprint(url_prefix='/api', blueprint=create_rest_api(self.sendor_queue, self.targets, self.file_stash))
		self.app = root.test_client()
	
	def test_file_stash(self):

		# Querying an empty file stash should return a file stash with a 'collection' element referencing an empty collection
		raw_response = self.app.get('/api/file_stash')
		response = json.loads(raw_response.data)
		self.assertIn('collection', response)
		self.assertEquals(len(response['collection']), 0)
	
		# Deleting a nonexistent file should result in "file not found"
		raw_response = self.app.delete('/api/file_stash/0')
		self.assertEquals(raw_response.status_code, 404)
		
		# Attempting to distribute a nonexistent file should result in a "file not found"
		raw_response = self.app.post('/api/file_stash/0/distribute/0')
		self.assertEquals(raw_response.status_code, 404)
		
	def test_tasks(self):

		# Querying an empty queue should return a response with a 'collection' element referencing an empty collection
		raw_response = self.app.get('/api/tasks')
		response = json.loads(raw_response.data)
		self.assertIn('collection', response)
		self.assertEquals(len(response['collection']), 0)

		# Querying a nonexistent task should result in a "task not found"
		raw_response = self.app.get('/api/tasks/0')
		response = json.loads(raw_response.data)
		self.assertEquals(raw_response.status_code, 404)
		
		# Attempting to cancel a nonexistent task should result in a "task not found"
		raw_response = self.app.put('/api/tasks/0/cancel')
		response = json.loads(raw_response.data)
		self.assertEquals(raw_response.status_code, 404)
		
	def test_targets(self):

		# Querying a non-empty set of targets should return a response with a 'collection' element referencing a non-collection of targets
		raw_response = self.app.get('/api/targets')
		response = json.loads(raw_response.data)
		self.assertIn('collection', response)
		self.assertNotEquals(len(response['collection']), 0)
		
	def tearDown(self):
		shutil.rmtree(self.work_directory)
		pass

if __name__ == '__main__':
	unittest.main()
