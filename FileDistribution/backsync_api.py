import backsync

def create_backsync_api(sendor_queue, targets, file_stash):

	@backsync.router('/api/file_stash')
	class FileStashHandler(backsync.BacksyncHandler):

		def read(self, *args, **kwargs):
			sorted_file_stash = sorted(file_stash.list(), cmp = lambda x, y: cmp(x.timestamp, y.timestamp))
			file_stash_contents = [file.to_json() for file in sorted_file_stash]
			return { 'collection' : file_stash_contents }

		def upsert(self, *args, **kwargs):
			raise NotImplementedError

		def delete(self, *args, **kwargs):
			raise NotImplementedError

	@backsync.router('/api/targets')
	class TargetsHandler(backsync.BacksyncHandler):

		def read(self, *args, **kwargs):
			target_list = targets.get_targets()
			targets_contents = [{ 'target_id' : target_id, 'name' : target_details['name'] } for (target_id, target_details) in target_list.iteritems()]
			return { 'collection' : targets_contents }

		def upsert(self, *args, **kwargs):
			raise NotImplementedError

		def delete(self, *args, **kwargs):
			raise NotImplementedError

	@backsync.router('/api/tasks')
	class TasksHandler(backsync.BacksyncHandler):

		def read(self, *args, **kwargs):
			tasks = sendor_queue.list()
			tasks_progress = [task.progress() for task in tasks]
			return { 'collection' : tasks_progress }

		def upsert(self, *args, **kwargs):
			raise NotImplementedError

		def delete(self, *args, **kwargs):
			raise NotImplementedError

	def tasks_notification(event_type, task):
		class SendorTasksModel(object):
			sync_name = '/api/tasks'

		if event_type == 'add' or event_type == 'change':
			backsync.BacksyncModelRouter.post_save(SendorTasksModel, task.progress())
		elif event_type == 'remove':
			backsync.BacksyncModelRouter.post_delete(SendorTasksModel, task.progress())
		else:
			raise NotImplementedError
			
	def file_stash_notification(event_type, stashed_file):
		class FileStashModel(object):
			sync_name = '/api/file_stash'

		if event_type == 'add' or event_type == 'change':
			backsync.BacksyncModelRouter.post_save(FileStashModel, stashed_file.to_json())
		elif event_type == 'remove':
			backsync.BacksyncModelRouter.post_delete(FileStashModel, stashed_file.to_json())
		else:
			raise NotImplementedError
			
	sendor_queue.subscribe(tasks_notification)
	file_stash.subscribe(file_stash_notification)
