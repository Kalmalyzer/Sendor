
import datetime

from abc import ABCMeta, abstractmethod

def format_datetime(time):
	return time.strftime("%Y-%m-%d %H:%M:%S")
	

def format_timedelta(duration):
	total_seconds = int(duration.total_seconds())
	seconds = total_seconds % 60
	days = total_seconds // (3600 * 24)
	hours = (total_seconds // 3600) % 24
	minutes = (total_seconds // 60) % 60
	
	result = str(seconds) + " seconds"
	if minutes > 0:
		result = str(minutes) + " minutes, " + result
	if hours > 0:
		result = str(hours) + " hours, " + result
	if days > 0:
		result = str(days) + " days, " + result
		
	return result


class SendorJob(object):

	def __init__(self, tasks=None):
		self.job_id = None
		self.work_directory = None
		self.enqueue_time = None
		self.start_time = None
		self.end_time = None
		if tasks:
			self.tasks = tasks
		else:
			self.tasks = []

	def started(self):
		self.start_time = datetime.datetime.utcnow()

	def completed(self):
		self.end_time = datetime.datetime.utcnow()

	def progress(self):
		status = { 'enqueue_time' : format_datetime(self.enqueue_time) }
		
		if self.start_time:
			if self.end_time:
				duration = self.end_time - self.start_time
			else:
				duration = datetime.datetime.utcnow() - self.start_time
			status['duration'] = format_timedelta(duration)

		tasks_status = []
		for task in self.tasks[0:]:
			task_status = { 'description' : task.string_description(),
							'state' : task.string_state(),
							'activity' : task.get_activity(),
							'progress' : task.get_progress(),
							'log' : task.get_log() }
			if task.start_time:
				if task.end_time:
					duration = task.end_time - task.start_time
				else:
					duration = datetime.datetime.utcnow() - task.start_time
				task_status['duration'] = format_timedelta(duration)
			
			tasks_status.append(task_status)

		status['tasks'] = tasks_status
			
		return status

	def set_queue_info(self, job_id, work_directory):
		self.job_id = job_id
		self.work_directory = work_directory
		self.enqueue_time = datetime.datetime.utcnow()
		
class SendorTask(object):

	NOT_STARTED = 0
	STARTED = 1
	COMPLETED = 2
	FAILED = 3
	CANCELED = 4
	
	def __init__(self):
		self.state = self.NOT_STARTED
		self.actions = []
		self.task_id = None
		self.work_directory = None
		self.start_time = None
		self.end_time = None
		self.progress = 0
		self.activity = ""
		self.log = ""

	def set_queue_info(self, task_id, work_directory):
		self.task_id = task_id
		self.work_directory = work_directory
		
	def started(self):
		self.state = self.STARTED
		self.start_time = datetime.datetime.utcnow()

	def completed(self):
		self.state = self.COMPLETED
		self.end_time = datetime.datetime.utcnow()

	def failed(self):
		self.state = self.FAILED
		self.end_time = datetime.datetime.utcnow()

	def canceled(self):
		self.state = self.CANCELED
		self.end_time = datetime.datetime.utcnow()

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

	def set_activity(self, activity):
		self.activity = activity

	def get_activity(self):
		return self.activity
		
	def set_progress(self, progress):
		self.progress = progress

	def get_progress(self):
		return self.progress
		
	def append_log(self, log):
		self.log = self.log + log

	def get_log(self):
		return self.log


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
	def activity(self, message):
		return

	@abstractmethod
	def progress(self, progress):
		return

	@abstractmethod
	def log(self, log):
		return

class SendorAction(object):
	__metaclass__ = ABCMeta
	
	@abstractmethod
	def run(self, context):
		return
