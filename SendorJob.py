
from abc import ABCMeta, abstractmethod


class SendorJob(object):

	def __init__(self, tasks=None):
		self.job_id = None
		self.work_directory = None
		if tasks:
			self.tasks = tasks
		else:
			self.tasks = []

	def started(self):
		pass

	def completed(self):
		pass

	def progress(self):
		status = []

		for task in self.tasks[0:]:
			status.append({ 'description' : task.string_description(),
							'state' : task.string_state(),
							'progress' : task.string_progress(),
							'details' : task.string_details() })
			
		return status

	def set_queue_info(self, job_id, work_directory):
		self.job_id = job_id
		self.work_directory = work_directory
		
class SendorTask(object):

	NOT_STARTED = 0
	STARTED = 1
	COMPLETED = 2
	FAILED = 3
	CANCELED = 4
	
	def __init__(self):
		self.state = self.NOT_STARTED
		self.progress = ""
		self.details = ""
		self.actions = []
		self.task_id = None
		self.work_directory = None

	def set_queue_info(self, task_id, work_directory):
		self.task_id = task_id
		self.work_directory = work_directory
		
	def started(self):
		self.state = self.STARTED

	def completed(self):
		self.state = self.COMPLETED

	def failed(self):
		self.state = self.FAILED

	def canceled(self):
		self.state = self.CANCELED

	def run(self, context):
		for action in self.actions:
			action.run(context)

	def string_description(self):
		raise Exception("No description given")

	def string_state(self):
		if self.state == self.NOT_STARTED:
			return 'not_started'
		elif self.state == self.STARTED:
			return 'in_progress'
		elif self.state == self.COMPLETED:
			return 'completed'
		elif self.state == self.FAILED:
			return 'failed'
		elif self.state == self.CANCELED:
			return 'canceled'
		else:
			raise Exception("Unknown state " + str(self.state))

	def string_details(self):
		return self.details

	def string_progress(self):
		return self.progress
		
	def set_progress(self, message):
		self.progress = message

	def append_details(self, string):
		self.details = self.details + string + "\n"


class SendorActionContext(object):
	__metaclass__ = ABCMeta

	def __init__(self, work_directory):
		self.work_directory = work_directory

	def translate_path(self, path):
		if self.work_directory:
			return path.replace('{task_work_directory}', self.work_directory)
		else:
			return path

	@abstractmethod
	def progress(self, message):
		return
			
class SendorAction(object):
	__metaclass__ = ABCMeta
	
	@abstractmethod
	def run(self, context):
		return
