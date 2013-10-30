
import os.path

import target_distribution_methods

from actions import ScpSendFileAction

def create_action(source, filename, target):	
	return ScpSendFileAction(source, filename, target)

target_distribution_methods.register('scp', create_action)
