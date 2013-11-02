
import os.path

import target_distribution_methods

from actions import ScpSendFileAction

def create_action(source, target):	
	return ScpSendFileAction(source, target)

target_distribution_methods.register('scp', create_action)
