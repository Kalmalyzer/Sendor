
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
	def __init__(self, task_id, work_directory, actions, cancel):
		self.task_id = task_id
		self.actions = actions
		self.work_directory = work_directory
		self.cancel = cancel

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

class SendorWorkerTask(Observable):

	def __init__(self, queue, max_task_execution_time, args):
		super(SendorWorkerTask, self).__init__()
		self.queue = queue
		self.max_task_execution_time = max_task_execution_time
		self.args = args
		self.queue_lock = threading.Lock()
		self.queue_active = True

	def enqueue(self, item, leave_queue_active):
		with self.queue_lock:
			if self.queue_active:
				self.queue.put(item)
				self.queue_active = leave_queue_active
		
	def enqueue_status(self, status):
		self.enqueue(StatusQueueItem(self.args.task_id, status), True)

	def enqueue_activity(self, activity):
		self.enqueue(ActivityQueueItem(self.args.task_id, activity), True)

	def enqueue_completion_ratio(self, completion_ratio):
		self.enqueue(CompletionRatioQueueItem(self.args.task_id, completion_ratio), True)

	def enqueue_log(self, log):
		self.enqueue(LogQueueItem(self.args.task_id, log), True)

	def enqueue_stdout(self, message):
		self.enqueue(StdOutQueueItem(self.args.task_id, message), True)

	def enqueue_task_done(self):
		self.enqueue(TaskDoneQueueItem(self.args.task_id), False)
	
	def run_actions_thread_func(self, actions, context):
		try:
			self.enqueue_status('started')
			self.enqueue_log("Task execution started")
			for action in actions:
				action.run(context)
			self.enqueue_status('completed')
			self.enqueue_log("Task execution completed")
		except:
			self.enqueue_status('failed')
			self.enqueue_log("Task execution failed due to exception. Callstack:")
			self.enqueue_log(traceback.format_exc())
	
	def wait_for_actions_thread_func(self, run_actions_thread, wait_done):
		run_actions_thread.join(self.max_task_execution_time)
		wait_done.set()
	
	def wait_for_cancel_thread_func(self, cancel, wait_done):
		cancel.wait()
		wait_done.set()
		
	def run(self):
		try:
			os.mkdir(self.args.work_directory)
			context = SendorWorkerActionContext(self, self.args.work_directory)

			wait_done = threading.Event()

			# Create threads for running actions, checking for cancellation, and timeout
			wait_for_cancel_thread = threading.Thread(target=(lambda self, cancel, wait_done: self.wait_for_cancel_thread_func(cancel, wait_done)), args=(self, self.args.cancel, wait_done))
			run_actions_thread = threading.Thread(target=(lambda self, actions, context: self.run_actions_thread_func(actions, context)), args=(self, self.args.actions, context))
			wait_for_actions_thread = threading.Thread(target=(lambda self, run_actions_thread, wait_done: self.wait_for_actions_thread_func(run_actions_thread, wait_done)), args=(self, run_actions_thread, wait_done))
			wait_for_cancel_thread.start()
			run_actions_thread.start()
			wait_for_actions_thread.start()

			# Wait for the actions to complete, cancel to be requested, or timeout to occur
			wait_done.wait()

			# Handle state transition
			if self.args.cancel.is_set():
				self.enqueue_status('canceled')
				self.enqueue_log("Task execution canceled")
			elif run_actions_thread.is_alive():
				self.enqueue_status('failed')
				self.enqueue_log("Task execution failed due to timeout -- more than " + str(self.max_task_execution_time) + " seconds, terminating task")

			# In case no cancel was selected, then let the cancellation thread complete
			self.args.cancel.set()
			wait_for_cancel_thread.join()

			# We cannot wait for the other two threads to complete since they can run for arbitrarily long
	
		except:
			self.enqueue_status('failed')
			self.enqueue_log("Task execution failed due to exception. Callstack:")
			self.enqueue_log(traceback.format_exc())
		finally:
			shutil.rmtree(self.args.work_directory, True)
			self.enqueue_task_done()

def start_sendor_worker_task(queue, max_task_execution_time, task_args):
	processor = SendorWorkerTask(queue, max_task_execution_time, task_args)
	processor.run()

class SendorWorker(Observable):

	class SendorTaskInFlight(object):
		def __init__(self, task, process, cancel, task_done):
			self.task = task
			self.process = process
			self.cancel = cancel
			self.task_done = task_done
			self.resolution_signaled = False
		
	def __init__(self, max_task_execution_time, max_task_finalization_time):
		super(SendorWorker, self).__init__()
		self.max_task_execution_time = max_task_execution_time
		self.max_task_finalization_time = max_task_finalization_time
		self.tasks_in_flight_lock = threading.RLock()
		self.tasks_in_flight = {}
		self.queue = multiprocessing.Queue()
		self.worker_thread = threading.Thread(target=(lambda self: self.worker_process_result_thread()), args=(self,))
		self.worker_thread.daemon = True
		self.worker_thread.start()

	def add(self, task):
		task_id = task.task_id
		cancel_event = multiprocessing.Event()
		task_done = threading.Event()
		task_args = SendorWorkerTaskArgs(task_id=task.task_id, work_directory=task.work_directory, actions=task.actions, cancel=cancel_event)
		with self.tasks_in_flight_lock:
			process = multiprocessing.Process(target=start_sendor_worker_task, args=(self.queue, self.max_task_execution_time, task_args))
			self.tasks_in_flight[task_id] = self.SendorTaskInFlight(task, process, cancel_event, task_done)
			process.start()

	def join(self, task):
		with self.tasks_in_flight_lock:
			task_in_flight = self.find_task_in_flight(task)
		if task_in_flight:
			task_in_flight.task_done.wait()

	def cancel(self, task):
		with self.tasks_in_flight_lock:
			task_in_flight = self.find_task_in_flight(task)
		if task_in_flight:
			task_in_flight.cancel.set()
				
	def find_task_in_flight(self, task):
		with self.tasks_in_flight_lock:
			tasks_in_flight = self.tasks_in_flight.values()[:]
			for task_in_flight in tasks_in_flight:
				if task_in_flight.task == task:
					return task_in_flight
			return None

	def finalize(self, task_id, task_in_flight):

		task_in_flight.process.join(self.max_task_finalization_time)
		if task_in_flight.process.is_alive():
			task.append_log("Process is still alive after join timeout; terminating forcefully")
			task_in_flight.process.terminate()
			task_in_flight.process.join()

		with self.tasks_in_flight_lock:
			del self.tasks_in_flight[task_id]

	def worker_process_result_thread(self):
		while True:
			item = self.queue.get()
			self.handle_worker_queue_item(item)
	
	def handle_worker_queue_item(self, item):
		task_id = item.task_id
		with self.tasks_in_flight_lock:
			task_in_flight = self.tasks_in_flight.get(task_id)
		
		task = task_in_flight.task
		
		if item.item_type == 'status':
			logger.debug("Status: " + item.status)
			if item.status == 'started':
				task.started()
			elif item.status == 'completed':
				if not task_in_flight.resolution_signaled:
					task.completed()
					task_in_flight.resolution_signaled = True
			elif item.status == 'failed':
				if not task_in_flight.resolution_signaled:
					task.failed()
					task_in_flight.resolution_signaled = True
			elif item.status == 'canceled':
				if not task_in_flight.resolution_signaled:
					task.canceled()
					task_in_flight.resolution_signaled = True
			else:
				raise Exception("Unknown status: " + item.status)

		elif item.item_type == 'activity':
			logger.debug("Activity: " + item.activity)
			task.set_activity(item.activity)
			task.append_log(item.activity)

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
			self.finalize(task_id, task_in_flight)
		else:
			raise Exception("Unknown type: " + item.item_type)

		if item.item_type == 'task_done':
			self.notify(event_type='remove', task=task)
			task_in_flight.task_done.set()
		else:
			self.notify(event_type='change', task=task)

class DummySendorAction(SendorAction):
	def run(self, context):
		context.activity("Dummy action initiated")
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
			task.enqueued(i, 'unittest/' + str(i))
			tasks.append(task)

		worker = SendorWorker(max_task_execution_time=10, max_task_finalization_time=1)
		for task in tasks:
			worker.add(task)
			
		for task in tasks:
			worker.join(task)

	def tearDown(self):
		shutil.rmtree('unittest')
	
if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	unittest.main()
