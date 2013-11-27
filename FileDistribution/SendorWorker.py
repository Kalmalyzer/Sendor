
import logging
import multiprocessing
import multiprocessing.queues
import os
import shutil
import thread
import threading
import traceback
import unittest

from SendorTask import SendorTask, SendorAction, SendorActionContext

from Observable import Observable

logger = logging.getLogger('SendorWorker')

class SendorWorkerTaskArgs(object):
	def __init__(self, task_in_flight_id, work_directory, actions):
		self.task_in_flight_id = task_in_flight_id
		self.actions = actions
		self.work_directory = work_directory

class QueueItem(object):
	def __init__(self, task_in_flight_id, item_type):
		self.task_in_flight_id = task_in_flight_id
		self.item_type = item_type

class StatusQueueItem(QueueItem):
	def __init__(self, task_in_flight_id, status):
		super(StatusQueueItem, self).__init__(task_in_flight_id, 'status')
		self.status = status

class ActivityQueueItem(QueueItem):
	def __init__(self, task_in_flight_id, activity):
		super(ActivityQueueItem, self).__init__(task_in_flight_id, 'activity')
		self.activity = activity

class CompletionRatioQueueItem(QueueItem):
	def __init__(self, task_in_flight_id, completion_ratio):
		super(CompletionRatioQueueItem, self).__init__(task_in_flight_id, 'completion_ratio')
		self.completion_ratio = completion_ratio

class LogQueueItem(QueueItem):
	def __init__(self, task_in_flight_id, log):
		super(LogQueueItem, self).__init__(task_in_flight_id, 'log')
		self.log = log

class StdOutQueueItem(QueueItem):
	def __init__(self, task_in_flight_id, message):
		super(StdOutQueueItem, self).__init__(task_in_flight_id, 'stdout')
		self.message = message

class TaskDoneQueueItem(QueueItem):
	def __init__(self, task_in_flight_id):
		super(TaskDoneQueueItem, self).__init__(task_in_flight_id, 'task_done')

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

class SendorWorkerTask(Observable):
	def __init__(self, queue, cancel, args):
		super(SendorWorkerTask, self).__init__()
		self.queue = queue
		self.cancel = cancel
		self.args = args

	def enqueue_status(self, status):
		self.queue.put(StatusQueueItem(self.args.task_in_flight_id, status))

	def enqueue_activity(self, activity):
		self.queue.put(ActivityQueueItem(self.args.task_in_flight_id, activity))

	def enqueue_completion_ratio(self, completion_ratio):
		self.queue.put(CompletionRatioQueueItem(self.args.task_in_flight_id, completion_ratio))

	def enqueue_log(self, log):
		self.queue.put(LogQueueItem(self.args.task_in_flight_id, log))

	def enqueue_stdout(self, message):
		self.queue.put(StdOutQueueItem(self.args.task_in_flight_id, message))

	def enqueue_task_done(self):
		self.queue.put(TaskDoneQueueItem(self.args.task_in_flight_id))
	
	def run(self):
		try:
			if self.cancel.is_set():
				self.enqueue_status('canceled')
			else:
				self.enqueue_status('started')
				os.mkdir(self.args.work_directory)
				context = SendorWorkerActionContext(self, self.args.work_directory)
				for action in self.args.actions:
					action.run(context)
				self.enqueue_status('completed')
		except:
			self.enqueue_status('failed')
			self.enqueue_stdout(traceback.format_exc())
		finally:
			shutil.rmtree(self.args.work_directory, True)
			self.enqueue_task_done()

def start_sendor_worker_task(args):
	processor = SendorWorkerTask(start_sendor_worker_task.queue, start_sendor_worker_task.cancel, args)
	processor.run()

def initialize_sendor_worker_process(queue, cancel):
	start_sendor_worker_task.queue = queue
	start_sendor_worker_task.cancel = cancel
	

class SendorWorker(Observable):

	unique_id = 0

	def __init__(self, num_processes):
		super(SendorWorker, self).__init__()
		self.num_processes = num_processes
		self.cancel = multiprocessing.Event()
		self.queue = multiprocessing.queues.SimpleQueue()
		self.pool = multiprocessing.Pool(processes=self.num_processes, initializer=initialize_sendor_worker_process, initargs=(self.queue, self.cancel))
		self.tasks_in_flight_lock = threading.RLock()
		self.tasks_in_flight = {}
		self.worker_thread = thread.start_new_thread((lambda sendor_worker: sendor_worker.worker_process_result_thread()), (self,))
		self.task_done = threading.Event()

	def worker_process_result_thread(self):
		while True:
			item = self.queue.get()
			self.handle_worker_queue_item(item)
	
	def handle_worker_queue_item(self, item):
		task_in_flight_id = item.task_in_flight_id
		with self.tasks_in_flight_lock:
			task = self.tasks_in_flight.get(task_in_flight_id)
		
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
			logger.debug("task_done")
			self.task_done.set()
			self.remove(task_in_flight_id)
		else:
			raise Exception("Unknown type: " + item.item_type)

		self.notify(event_type='change', task=task)

#	def cancel_current_job(self):
#		self.cancel.set()

	def add(self, task):
		self.notify(event_type='add', task=task)
		task_in_flight_id = self.unique_id
		task_args = SendorWorkerTaskArgs(task_in_flight_id=task_in_flight_id, work_directory=task.work_directory, actions=task.actions)
		with self.tasks_in_flight_lock:
			self.tasks_in_flight[task_in_flight_id] = task
			self.unique_id += 1
		self.pool.apply_async(start_sendor_worker_task, (task_args, ))

	def remove(self, task_in_flight_id):
		with self.tasks_in_flight_lock:
			task = self.tasks_in_flight.get(task_in_flight_id)
			self.notify(event_type='remove', task=task)
			del self.tasks_in_flight[task_in_flight_id]
		
	def join(self, task):
		while True:
			with self.tasks_in_flight_lock:
				tasks = self.tasks_in_flight.values()[:]
			if not task in tasks:
				break
			self.task_done.wait()
		
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
			task.set_queue_info(i, 'unittest/' + str(i))
			tasks.append(task)

		processing = SendorWorker(4)
		for task in tasks:
			processing.add(task)

		for task in tasks:
			processing.join(task)
	
	def tearDown(self):
		shutil.rmtree('unittest')
	
if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	unittest.main()
