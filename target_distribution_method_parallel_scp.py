
import os.path

import target_distribution_methods

from actions import ParallelScpSendFileAction

def create_action(source, filename, target):	
	return ParallelScpSendFileAction(source, filename, target)

target_distribution_methods.register('parallel_scp', create_action)
