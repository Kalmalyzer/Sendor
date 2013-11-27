
import logging
import os
import shutil
import thread
import threading
import traceback
import unittest

from flask import render_template

from SendorWorker import SendorWorker
from SendorTask import SendorTask

logger = logging.getLogger('SendorQueue')

class SendorQueue(object):

	unique_id = 0

	def __init__(self, num_processes, work_directory):
		self.work_directory = work_directory
		self.tasks_work_directory = os.path.join(self.work_directory, 'active_tasks')
		shutil.rmtree(self.tasks_work_directory, ignore_errors=True)
		os.mkdir(self.tasks_work_directory)
		self.tasks_lock = threading.RLock()
		self.tasks = []
		self.worker = SendorWorker(num_processes)

	def add(self, task):
		task_id = self.unique_id
		self.unique_id = self.unique_id + 1
		task_work_directory = os.path.join(self.tasks_work_directory, str(task_id))
		with self.tasks_lock:
			task.set_queue_info(task_id, task_work_directory)
			self.tasks.append(task)
		self.worker.add(task)

	def list(self):
		with self.tasks_lock:
			return self.tasks[:]
		
	def wait(self):
		tasks = self.list()
		for task in tasks:
			self.worker.join(task)

#	def cancel_current_job(self):
#		self.worker_thread.cancel_current_job()
		

class SendorQueueUnitTest(unittest.TestCase):

	work_directory = 'unittest'

	def setUp(self):
		os.mkdir(self.work_directory)
		self.sendor_queue = SendorQueue(4, self.work_directory)

	def test_single_task(self):

		NOT_STARTED_TASK = 0
		STARTED_TASK = 1
		COMPLETED_TASK = 2

		class State(object):
			def __init__(self, unittest):
				self.state = NOT_STARTED_TASK
				self.unittest = unittest

		state = State(self)

		class InstrumentedSendorTask(SendorTask):
			
			def started(self):
				state.unittest.assertEquals(state.state, NOT_STARTED_TASK)
				state.state = STARTED_TASK
				super(InstrumentedSendorTask, self).started()

			def completed(self):
				super(InstrumentedSendorTask, self).completed()
				state.unittest.assertEquals(state.state, STARTED_TASK)
				state.state = COMPLETED_TASK

		def notification(event_type, task):
			print event_type + " " + str(task.task_id)
		
		self.sendor_queue.worker.subscribe(notification)
				
		task = InstrumentedSendorTask()
		self.sendor_queue.add(task)
		self.sendor_queue.wait()
		self.assertEquals(state.state, COMPLETED_TASK)

	def tearDown(self):
		shutil.rmtree(self.work_directory)

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	unittest.main()
