
import logging
import multiprocessing
import multiprocessing.queues
import os
import shutil
import unittest
import traceback

from SendorJob import SendorJob, SendorTask, SendorAction, SendorActionContext

logger = logging.getLogger('SendorWorker')

class SendorWorkerTaskArgs(object):
	def __init__(self, task_id, work_directory, actions):
		self.task_id = task_id
		self.actions = actions
		self.work_directory = work_directory

class QueueItem(object):
	def __init__(self, task_id, item_type):
		self.task_id = task_id
		self.item_type = item_type

class StatusQueueItem(QueueItem):
	def __init__(self, task_id, status):
		super(StatusQueueItem, self).__init__(task_id, 'status')
		self.status = status

class ActivityQueueItem(QueueItem):
	def __init__(self, task_id, activity):
		super(ActivityQueueItem, self).__init__(task_id, 'activity')
		self.activity = activity

class CompletionRatioQueueItem(QueueItem):
	def __init__(self, task_id, completion_ratio):
		super(CompletionRatioQueueItem, self).__init__(task_id, 'completion_ratio')
		self.completion_ratio = completion_ratio

class LogQueueItem(QueueItem):
	def __init__(self, task_id, log):
		super(LogQueueItem, self).__init__(task_id, 'log')
		self.log = log

class StdOutQueueItem(QueueItem):
	def __init__(self, task_id, message):
		super(StdOutQueueItem, self).__init__(task_id, 'stdout')
		self.message = message

class TaskDoneQueueItem(QueueItem):
	def __init__(self, task_id):
		super(TaskDoneQueueItem, self).__init__(task_id, 'task_done')

class SendorWorkerActionContext(SendorActionContext):
	def __init__(self, worker_task, work_directory):
		super(SendorWorkerActionContext, self).__init__(work_directory)
		self.worker_task = worker_task
		
	def activity(self, activity):
		self.worker_task.enqueue_activity(activity)

	def completion_ratio(self, completion_ratio):
		self.worker_task.enqueue_completion_ratio(completion_ratio)

	def log(self, log):
		self.worker_task.enqueue_log(log)

class SendorWorkerTask(object):
	def __init__(self, queue, cancel, args):
		self.queue = queue
		self.cancel = cancel
		self.args = args

	def enqueue_status(self, status):
		self.queue.put(StatusQueueItem(self.args.task_id, status))

	def enqueue_activity(self, activity):
		self.queue.put(ActivityQueueItem(self.args.task_id, activity))

	def enqueue_completion_ratio(self, completion_ratio):
		self.queue.put(CompletionRatioQueueItem(self.args.task_id, completion_ratio))

	def enqueue_log(self, log):
		self.queue.put(LogQueueItem(self.args.task_id, log))

	def enqueue_stdout(self, message):
		self.queue.put(StdOutQueueItem(self.args.task_id, message))

	def enqueue_task_done(self):
		self.queue.put(TaskDoneQueueItem(self.args.task_id))
	
	def run(self):
		try:
			if self.cancel.is_set():
				self.enqueue_status('canceled')
			else:
				self.enqueue_status('started')
				context = SendorWorkerActionContext(self, self.args.work_directory)
				for action in self.args.actions:
					action.run(context)
				self.enqueue_status('completed')
		except:
			self.enqueue_status('failed')
			self.enqueue_stdout(traceback.format_exc())
		finally:
			self.enqueue_task_done()

def start_sendor_worker_task(args):
	processor = SendorWorkerTask(start_sendor_worker_task.queue, start_sendor_worker_task.cancel, args)
	processor.run()

def initialize_sendor_worker_process(queue, cancel):
	start_sendor_worker_task.queue = queue
	start_sendor_worker_task.cancel = cancel
	

class SendorWorker(object):

	def __init__(self, num_processes):
		self.num_processes = num_processes
		self.cancel = multiprocessing.Event()

	def cancel_current_job(self):
		self.cancel.set()

	def run_job(self, job):
			
		os.mkdir(job.work_directory)
		for task in job.tasks:
			os.mkdir(task.work_directory)

		job.started()
		self.run_tasks(job.tasks)
		job.completed()
			
		shutil.rmtree(job.work_directory)
		
	def run_tasks(self, tasks):
	
		self.cancel.clear()
		queue = multiprocessing.queues.SimpleQueue()
		pool = multiprocessing.Pool(processes=self.num_processes, initializer=initialize_sendor_worker_process, initargs=(queue, self.cancel))

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
				logger.debug("Status: " + item.status)
				if item.status == 'started':
					task.started()
				elif item.status == 'completed':
					task.completed()
				elif item.status == 'failed':
					task.failed()
				elif item.status == 'canceled':
					task.canceled()
				else:
					raise Error("Unknown status: " + item.status)
					
			elif item.item_type == 'activity':
				logger.debug("Activity: " + item.activity)
				task.set_activity(item.activity)

			elif item.item_type == 'completion_ratio':
				logger.debug("Completion ratio: " + str(int(item.completion_ratio * 100)) + "%")
				task.set_completion_ratio(item.completion_ratio)

			elif item.item_type == 'log':
				logger.debug("Log: " + item.log)
				task.append_log(item.log)

			elif item.item_type == 'stdout':
				logger.debug("Stdout: " + item.message)
				task.append_log(item.message)

			elif item.item_type == 'task_done':
				tasks_left -= 1
				logger.debug("tasks_left: " + str(tasks_left))
			else:
				raise Exception("Unknown type: " + item.item_type)

		logger.debug("waiting for all pools to complete")
		pool.close()
		pool.join()
		logger.debug("all pools completed")

class DummySendorAction(SendorAction):
	def run(self, context):
		context.activity("Dummy action initiated")
		logger.info("Executing dummy sendor action")
		context.completion_ratio(0.1)
		context.completion_ratio(0.9)
		context.activity("Dummy action completed")
			
class SendorTaskProcessUnitTest(unittest.TestCase):

	def setUp(self):
		os.mkdir('unittest')
	
	def test_sendor_worker_run(self):

		tasks = []
		for i in range(5):
			task = SendorTask()
			task.actions = [DummySendorAction()]
			task.set_queue_info(i, 'unittest/job/' + str(i))
			tasks.append(task)

		job = SendorJob(tasks)
		job.set_queue_info(0, 'unittest/job')

		processing = SendorWorker(4)
		processing.run_job(job)
	
		pass
	
	def tearDown(self):
		shutil.rmtree('unittest')
	
if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	unittest.main()
