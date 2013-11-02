
import os.path

import target_distribution_methods

from actions import ParallelScpSendFileAction

def create_action(source, filename, sha1sum, size, target):	
	return ParallelScpSendFileAction(source, filename, sha1sum, size, target)

target_distribution_methods.register('parallel_scp', create_action)
