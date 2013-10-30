
from SendorQueue import SendorTask

class DistributeFileTask(SendorTask):

	def __init__(self, source, target):
		super(DistributeFileTask, self).__init__()
		self.source = source
		self.target = target

	def string_description(self):
		return "Distribute file " + self.source + " to " + self.target
