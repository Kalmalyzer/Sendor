
import multiprocessing
import multiprocessing.queues
import os
import shutil
import unittest
import thread
import traceback

import Queue

from SendorJob import SendorTask, SendorAction, SendorActionContext


class SendorWorkerTaskArgs(object):
	def __init__(self, task_id, work_directory, actions):
		self.task_id = task_id
		self.actions = actions
		self.work_directory = work_directory

class QueueItem(object):
	def __init__(self, task_id, item_type):
		self.task_id = task_id
		self.item_type = item_type

class StdOutQueueItem(QueueItem):
	def __init__(self, task_id, message):
		super(StdOutQueueItem, self).__init__(task_id, 'stdout')
		self.message = message

class StatusQueueItem(QueueItem):
	def __init__(self, task_id, status):
		super(StatusQueueItem, self).__init__(task_id, 'status')
		self.status = status

class TaskDoneQueueItem(QueueItem):
	def __init__(self, task_id):
		super(TaskDoneQueueItem, self).__init__(task_id, 'task_done')

class SendorWorkerActionContext(SendorActionContext):
	def __init__(self, work_directory):
		super(SendorWorkerActionContext, self).__init__(work_directory)

class SendorWorkerTask(object):
	def __init__(self, queue, args):
		self.queue = queue
		self.args = args

	def enqueue_status(self, status):
		self.queue.put(StatusQueueItem(self.args.task_id, status))

	def enqueue_stdout(self, message):
		self.queue.put(StdOutQueueItem(self.args.task_id, message))

	def enqueue_task_done(self):
		self.queue.put(TaskDoneQueueItem(self.args.task_id))
	
	def run(self):
		try:
			self.enqueue_status('started')
			context = SendorWorkerActionContext(self.args.work_directory)
			for action in self.args.actions:
				action.run(context)
			self.enqueue_status('completed')
		except:
			self.enqueue_status('failed')
			self.enqueue_stdout(traceback.format_exc())
		finally:
			self.enqueue_task_done()

def start_sendor_worker_task(args):
	processor = SendorWorkerTask(start_sendor_worker_task.queue, args)
	processor.run()

def initialize_sendor_worker_process(queue):
	start_sendor_worker_task.queue = queue
	
class SendorWorker(object):

	def __init__(self, num_processes, pending_jobs, past_jobs):
		self.num_processes = num_processes
		self.pending_jobs = pending_jobs
		self.past_jobs = past_jobs
		thread.start_new_thread((lambda sendor_worker: sendor_worker.sendor_processing_thread()), (self,))
		self.current_job = None

	def sendor_processing_thread(self):
	
		while True:
			print "before get"
			job = self.pending_jobs.get()
			print "after get"
			self.current_job_is_canceled = False
			self.current_job = job

			os.mkdir(job.work_directory)
			for task in job.tasks:
				os.mkdir(task.work_directory)

			job.started()
			self.run(job.tasks)
			job.completed()
				
			shutil.rmtree(job.work_directory)

			self.current_job = None
			self.pending_jobs.task_done()
			self.past_jobs.put(job)

	def run(self, tasks):
	
		queue = multiprocessing.queues.SimpleQueue()
		pool = multiprocessing.Pool(processes=self.num_processes, initializer=initialize_sendor_worker_process, initargs=(queue,))

		tasks_args = []

		for i in range(len(tasks)):
			task = tasks[i]
			task_args = SendorWorkerTaskArgs(task_id=i, work_directory = task.work_directory, actions=task.actions)
			tasks_args.append(task_args)
			pool.apply_async(start_sendor_worker_task, (task_args, ))
		
		tasks_left = len(tasks)
		while tasks_left > 0:
			item = queue.get()
			
			task_id = item.task_id
			task = tasks[task_id]
			
			if item.item_type == 'status':
				print "Status: " + str(item.status)
				if item.status == 'started':
					task.started()
				elif item.status == 'completed':
					task.completed()
				elif item.status == 'failed':
					task.failed()
				else:
					raise Error("Unknown status: " + item.status)
					
			elif item.item_type == 'stdout':
				print "Message: " + item.message
				task.append_details(item.message)

			elif item.item_type == 'task_done':
				tasks_left -= 1
				print "tasks_left: " + str(tasks_left)
			else:
				raise Error("Unknown type: " + item.item_type)

		print "waiting for all pools to complete"
		pool.close()
		pool.join()
	

class DummySendorAction(SendorAction):
	def run(self, context):
		print "Executing dummy sendor action"
			
class SendorTaskProcessUnitTest(unittest.TestCase):

	def setUp(self):
		pass
	
	def test_sendor_worker_run(self):

		tasks = []
		for i in range(5):
			task = SendorTask()
			task.actions = [DummySendorAction()]
			tasks.append(task)

		processing = SendorWorker(4, Queue.Queue(), Queue.Queue())
		processing.run(tasks)
	
		pass
	
	def tearDown(self):
		pass
	
if __name__ == '__main__':
	unittest.main()
