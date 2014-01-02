
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
		self.enqueue_time = None
		self.start_time = None
		self.end_time = None
		self.completion_ratio = 0
		self.activity = ""
		self.log = ""
		self.is_cancelable = False

	def enqueued(self, task_id, work_directory):
		self.task_id = task_id
		self.work_directory = work_directory
		self.enqueue_time = datetime.datetime.utcnow()
		
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
		
	def set_completion_ratio(self, completion_ratio):
		self.completion_ratio = completion_ratio

	def get_completion_ratio(self):
		return self.completion_ratio
		
	def append_log(self, log):
		self.log = self.log + log + "\n"

	def get_log(self):
		return self.log

	def progress(self):
		duration_string = None
		if self.start_time:
			if self.end_time:
				duration = self.end_time - self.start_time
			else:
				duration = datetime.datetime.utcnow() - self.start_time
			duration_string = format_timedelta(duration)

		enqueue_time_string = None
		if self.enqueue_time:
			enqueue_time_string = format_datetime(self.enqueue_time)

		status = { 'task_id' : self.task_id,
			'description' : self.string_description(),
			'enqueue_time' : enqueue_time_string,
			'duration' : duration_string,
			'state' : self.string_state(),
			'activity' : self.get_activity(),
			'completion_ratio' : self.get_completion_ratio(),
			'is_cancelable' : self.is_cancelable,
			'log' : self.get_log() }
			
		return status

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
	def completion_ratio(self, action_completion_ratio):
		return

	@abstractmethod
	def log(self, log):
		return

class SendorAction(object):
	__metaclass__ = ABCMeta

	def __init__(self, completion_weight):
		self.completion_weight = completion_weight
	
	@abstractmethod
	def run(self, context):
		return
