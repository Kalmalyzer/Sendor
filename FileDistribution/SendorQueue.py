
import datetime
import logging
import os
import shutil
import thread
import threading
import time
import traceback
import unittest

from flask import render_template

from SendorWorker import SendorWorker
from SendorTask import SendorTask, SendorAction

from Observable import Observable

logger = logging.getLogger('SendorQueue')

class SendorQueue(Observable):

	class Error(Exception):
		pass

	class TaskNotFoundError(Error):
		pass
	
	class TaskHasCompletedError(Error):
		pass
		
	class TaskHasNotCompletedError(Error):
		pass
	
	unique_id = 0

	def __init__(self, num_processes, work_directory, max_task_execution_time, max_task_finalization_time, task_cleanup_interval_seconds, max_task_wait_seconds, max_task_exist_days):
		super(SendorQueue, self).__init__()
		self.num_processes = num_processes
		self.work_directory = work_directory
		self.tasks_work_directory = os.path.join(self.work_directory, 'active_tasks')
		shutil.rmtree(self.tasks_work_directory, ignore_errors=True)
		os.mkdir(self.tasks_work_directory)
		self.tasks_lock = threading.RLock()
		self.tasks = []
		self.worker = SendorWorker(max_task_execution_time, max_task_finalization_time)
		self.nonprocessed_tasks = []
		self.worker_tasks = []
		self.task_done = threading.Event()
		
		def notifier(**kwargs):
			if kwargs['event_type'] == 'change':
				with self.tasks_lock:
					self.notify(**kwargs)
			elif kwargs['event_type'] == 'remove':
				with self.tasks_lock:
					task = kwargs['task']
					self.worker_tasks.remove(task)
					self.task_done.set()
				task.is_cancelable = False
				self.notify(event_type='change', task=task)
				self.process_next_task_if_available()
		
		self.worker.subscribe(notifier)

		if task_cleanup_interval_seconds:
			cleanup_thread = threading.Thread(target=(lambda self, task_cleanup_interval_seconds, max_task_wait_seconds, max_task_exist_days: self.cleanup_thread_func(task_cleanup_interval_seconds, max_task_wait_seconds, max_task_exist_days)), args=(self, task_cleanup_interval_seconds, max_task_wait_seconds, max_task_exist_days))
			cleanup_thread.daemon = True
			cleanup_thread.start()
	
	def cleanup_thread_func(self, task_cleanup_interval_seconds, max_task_wait_seconds, max_task_exist_days):
		while True:
			time.sleep(task_cleanup_interval_seconds)
			now = datetime.datetime.utcnow()
			tasks_to_cancel = []
			tasks_to_remove = []
			with self.tasks_lock:

				max_nonprocessed_timedelta = datetime.timedelta(seconds=max_task_wait_seconds)
				for task in self.nonprocessed_tasks:
					age = now - task.enqueue_time
					if age > max_nonprocessed_timedelta:
						tasks_to_cancel.append(task)

				max_exist_timedelta = datetime.timedelta(days=max_task_exist_days)
				for task in self.tasks:
					age = now - task.enqueue_time
					if age > max_exist_timedelta:
						tasks_to_remove.append(task)

			for task in tasks_to_cancel:
				try:
					self.cancel(task)
					logger.info("Cancelled task " + str(task.task_id) + " since it had been waiting for too long")
				except Exception, e:
					logger.error("Exception: " + e.message)
					logger.error(traceback.format_exc())

			for task in tasks_to_remove:
				try:
					self.remove(task)
					logger.info("Removed task " + str(task.task_id) + " since it was too old")
				except Exception, e:
					logger.error("Exception: " + e.message)
					logger.error(traceback.format_exc())

	def process_next_task_if_available(self):
		with self.tasks_lock:
			if len(self.worker_tasks) < self.num_processes and self.nonprocessed_tasks:
				task = self.nonprocessed_tasks.pop()
				self.worker_tasks.append(task)
				self.worker.add(task)
		
	def add(self, task):
		task_id = self.unique_id
		self.unique_id = self.unique_id + 1
		task_work_directory = os.path.join(self.tasks_work_directory, str(task_id))
		with self.tasks_lock:
			task.enqueued(task_id, task_work_directory)
			self.nonprocessed_tasks.append(task)
			self.tasks.append(task)
			task.is_cancelable = True
			self.notify(event_type='add', task=task)
		self.process_next_task_if_available()

	def list(self):
		with self.tasks_lock:
			return self.tasks[:]
		
	def get(self, task_id):
		with self.tasks_lock:
			for task in self.tasks:
				if task.task_id == task_id:
					return task
			raise self.TaskNotFoundError("Task with id " + str(task_id) + " does not exist in SendorQueue")
	
	def join(self, task):
		while True:
			with self.tasks_lock:
				self.task_done.clear()
				if task not in self.nonprocessed_tasks and task not in self.worker_tasks:
					return

				wait_for_worker = task in self.worker_tasks

			if wait_for_worker:
				self.worker.join(task)
				return
			
			self.task_done.wait()
			
	def wait(self):
		with self.tasks_lock:
			tasks = self.list()
		for task in tasks:
			self.join(task)
	
	def cancel(self, task):
		with self.tasks_lock:
			if task in self.nonprocessed_tasks:
				task.canceled()
				self.nonprocessed_tasks.remove(task)
				self.notify(event_type='change', task=task)
			elif task in self.worker_tasks:
				self.worker.cancel(task)
			else:
				raise self.TaskHasCompletedError("Task " + str(task.task_id) + " has already completed execution")

	def remove(self, task):
		with self.tasks_lock:
			if not task in self.tasks:
				raise self.TaskNotFoundError("Task " + str(task.task_id) + " does not exist in SendorQueue")
			if task in self.nonprocessed_tasks or task in self.worker_tasks:
				raise self.TaskHasNotCompletedError("Task " + str(task.task_id) + " has not completed processing in SendorQueue")
			else:
				self.tasks.remove(task)
				self.notify(event_type='remove', task=task)

class SendorQueueUnitTest(unittest.TestCase):

	work_directory = 'unittest'

	def setUp(self):
		os.mkdir(self.work_directory)
		self.sendor_queue = SendorQueue(num_processes=2, work_directory=self.work_directory, max_task_execution_time=10, max_task_finalization_time=1, task_cleanup_interval_seconds=None, max_task_wait_seconds=None, max_task_exist_days=None)

	def test_multiple_tasks(self):

		class DummySendorAction(SendorAction):
			def run(self, context):
				context.activity("Dummy action invoked")

		tasks = []
		for i in range(5):
			task = SendorTask()
			task.actions = [DummySendorAction()]
			task.enqueued(i, 'unittest/' + str(i))
			tasks.append(task)

		for task in tasks:
			self.sendor_queue.add(task)
			
		for task in tasks:
			self.sendor_queue.join(task)

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
		self.sendor_queue.remove(task)

	def tearDown(self):
		shutil.rmtree(self.work_directory)

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	unittest.main()
