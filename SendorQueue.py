
import os
import shutil
import thread
import unittest

from Queue import Queue

from flask import render_template

import traceback

class SendorJob(object):

	def __init__(self, tasks=None):
		self.id = None
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
							'details' : task.string_details() })
			
		return status

	def set_queue_info(self, id, work_directory):
		self.id = id
		self.work_directory = work_directory
		
class SendorTask(object):

	NOT_STARTED = 0
	STARTED = 1
	COMPLETED = 2
	FAILED = 3
	CANCELED = 4
	
	def __init__(self):
		self.state = self.NOT_STARTED
		self.details = ""
		self.actions = []
		self.id = None
		self.work_directory = None

	def set_queue_info(self, id, work_directory):
		self.id = id
		self.work_directory = work_directory
		
	def started(self):
		self.state = self.STARTED

	def completed(self):
		self.state = self.COMPLETED

	def failed(self):
		self.state = self.FAILED

	def canceled(self):
		self.state = self.CANCELED

	def run(self):
		for action in self.actions:
			action.run()

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

	def append_details(self, string):
		self.details = self.details + string + "\n"

	def translate_path(self, path):
		if self.work_directory:
			return path.replace('{task_work_directory}', self.work_directory)
		else:
			return path
		
class SendorAction(object):

	def __init__(self, task):
		self.task = task

class SendorQueue():

	unique_id = 0

	def __init__(self, work_directory):

		self.work_directory = work_directory
		self.pending_jobs = Queue()
		self.current_job = None
		self.past_jobs = Queue()
		thread.start_new_thread((lambda sendor_queue: sendor_queue.job_worker_thread()), (self,))

	def job_worker_thread(self):
		while True:

			job = self.pending_jobs.get()
			self.current_job_is_canceled = False
			self.current_job = job

			os.mkdir(job.work_directory)
			for task in job.tasks:
				os.mkdir(task.work_directory)
			
			job.started()

			for task in job.tasks:

				if self.current_job_is_canceled:
					task.canceled()
				else:
					try:
						task.started()
						task.run()
						task.completed()
					except:
						task.append_details(traceback.format_exc())
						task.failed()
						traceback.print_exc()

			job.completed()
			
			shutil.rmtree(job.work_directory)

			self.current_job = None

			self.pending_jobs.task_done()

			self.past_jobs.put(job)

	def add(self, job):
		job_id = self.unique_id
		job_work_directory = os.path.join(self.work_directory, 'current_job')
		job.set_queue_info(id, job_work_directory)
		self.unique_id = self.unique_id + 1

		task_id = 0
		for task in job.tasks:
			task_work_directory = os.path.join(job_work_directory, str(task_id))
			task.set_queue_info(task_id, task_work_directory)
			task_id = task_id + 1

		self.pending_jobs.put(job)
		return job

	def wait(self):
		self.pending_jobs.join()

	def cancel_current_job(self):
		self.current_job_is_canceled = True
		

class SendorQueueUnitTest(unittest.TestCase):

	work_directory = 'unittest'

	def setUp(self):
		os.mkdir(self.work_directory)
		self.sendor_queue = SendorQueue(self.work_directory)

	def test_empty_job(self):

		NOT_STARTED_JOB = 0
		STARTED_JOB = 1
		COMPLETED_JOB = 2

		class State:
			def __init__(self, unittest):
				self.state = NOT_STARTED_JOB
				self.unittest = unittest

		state = State(self)
		
		class InstrumentedSendorJob(SendorJob):

			def started(self):
				state.unittest.assertEquals(state.state, NOT_STARTED_JOB)
				state.state = STARTED_JOB
				super(InstrumentedSendorJob, self).started()

			def completed(self):
				super(InstrumentedSendorJob, self).completed()
				state.unittest.assertEquals(state.state, STARTED_JOB)
				state.state = COMPLETED_JOB

		job = InstrumentedSendorJob([])
		self.sendor_queue.add(job)
		self.sendor_queue.wait()
		self.assertEquals(state.state, COMPLETED_JOB)

	def test_job_with_single_task(self):

		NOT_STARTED_JOB = 0
		STARTED_JOB = 1
		STARTED_TASK = 2
		COMPLETED_TASK = 3
		COMPLETED_JOB = 4

		class State(object):
			def __init__(self, unittest):
				self.state = NOT_STARTED_JOB
				self.unittest = unittest

		state = State(self)

		class InstrumentedSendorJob(SendorJob):

			def started(self):
				state.unittest.assertEquals(state.state, NOT_STARTED_JOB)
				state.state = STARTED_JOB
				super(InstrumentedSendorJob, self).started()

			def completed(self):
				super(InstrumentedSendorJob, self).completed()
				state.unittest.assertEquals(state.state, COMPLETED_TASK)
				state.state = COMPLETED_JOB

		class InstrumentedSendorTask(SendorTask):
			
			def started(self):
				state.unittest.assertEquals(state.state, STARTED_JOB)
				state.state = STARTED_TASK
				super(InstrumentedSendorTask, self).started()

			def completed(self):
				super(InstrumentedSendorTask, self).completed()
				state.unittest.assertEquals(state.state, STARTED_TASK)
				state.state = COMPLETED_TASK
		
		task = InstrumentedSendorTask()
		job = InstrumentedSendorJob([task])
		self.sendor_queue.add(job)
		self.sendor_queue.wait()
		self.assertEquals(state.state, COMPLETED_JOB)

	def tearDown(self):
		shutil.rmtree(self.work_directory)

if __name__ == '__main__':
	unittest.main()
