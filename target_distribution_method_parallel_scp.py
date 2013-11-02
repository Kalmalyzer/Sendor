
import os.path

import target_distribution_methods

from actions import ParallelScpSendFileAction

def create_action(source, target):	
	return ParallelScpSendFileAction(source, target)

target_distribution_methods.register('parallel_scp', create_action)
