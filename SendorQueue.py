
import logging
import os
import shutil
import thread
import traceback
import unittest

from Queue import Queue

from flask import render_template

from SendorWorker import SendorWorker
from SendorJob import SendorJob, SendorTask

logger = logging.getLogger('SendorQueue')

class SendorWorkerThread(object):

	def __init__(self, num_processes, pending_jobs, past_jobs):
		self.pending_jobs = pending_jobs
		self.past_jobs = past_jobs
		thread.start_new_thread((lambda sendor_worker_thread: sendor_worker_thread.sendor_processing_thread()), (self,))
		self.current_job = None
		self.worker = SendorWorker(num_processes)

	def sendor_processing_thread(self):
	
		while True:
			logger.debug("waiting for any jobs to be enqueued")
			job = self.pending_jobs.get()
			logger.debug("processing job")
			self.current_job_is_canceled = False
			self.current_job = job

			self.worker.run_job(job)

			self.current_job = None
			self.pending_jobs.task_done()
			self.past_jobs.put(job)

	def cancel_current_job(self):
		self.worker.cancel_current_job()

class SendorQueue(object):

	unique_id = 0

	def __init__(self, num_processes, work_directory):

		self.work_directory = work_directory
		self.job_work_directory = os.path.join(self.work_directory, 'current_job')
		shutil.rmtree(self.job_work_directory, ignore_errors=True)
		self.pending_jobs = Queue()
		self.past_jobs = Queue()
		self.worker_thread = SendorWorkerThread(num_processes, self.pending_jobs, self.past_jobs)

	def add(self, job):
		job_id = self.unique_id
		job.set_queue_info(job_id, self.job_work_directory)
		self.unique_id = self.unique_id + 1

		task_id = 0
		for task in job.tasks:
			task_work_directory = os.path.join(self.job_work_directory, str(task_id))
			task.set_queue_info(task_id, task_work_directory)
			task_id = task_id + 1

		self.pending_jobs.put(job)
		return job

	def wait(self):
		self.pending_jobs.join()

	def cancel_current_job(self):
		self.worker_thread.cancel_current_job()
		

class SendorQueueUnitTest(unittest.TestCase):

	work_directory = 'unittest'

	def setUp(self):
		os.mkdir(self.work_directory)
		self.sendor_queue = SendorQueue(4, self.work_directory)

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
