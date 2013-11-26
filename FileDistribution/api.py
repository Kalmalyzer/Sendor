
import logging

from flask import Blueprint, Response, jsonify

from SendorTask import SendorTask

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

def create_api(sendor_queue, targets, file_stash):

	api_app = Blueprint('api', __name__)

	@api_app.route('/tasks', methods = ['GET'])
	def tasks_get():
		tasks = sendor_queue.list()
		tasks_progress = [task.progress() for task in tasks]
		return jsonify(collection=tasks_progress)

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

	@api_app.route('/file_stash/<file_id>/delete', methods = ['DELETE'])
	def file_stash_delete(file_id):
		file_stash.remove(file_id)
		return ""
	
	@api_app.route('/file_stash/<file_id>/distribute/<target_id>', methods = ['POST'])
	def file_stash_distribute(file_id, target_id):
		stashed_file = file_stash.lock(file_id)

		try:
			distribute_file_task = DistributeFileTask(file_stash, stashed_file.original_filename, target_id, file_id)
			distribute_file_actions = targets.create_distribution_actions(stashed_file.full_path_filename, stashed_file.original_filename, stashed_file.physical_file.sha1sum, stashed_file.size, target_id)
			distribute_file_task.actions.extend(distribute_file_actions)
			sendor_queue.add(distribute_file_task)
		finally:
			file_stash.unlock(stashed_file)
	
		return ""

	return api_app
