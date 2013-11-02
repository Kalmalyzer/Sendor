
import os.path

import target_distribution_methods

from actions import ScpSendFileAction

def create_action(source, filename, sha1sum, size, target):	
	return ScpSendFileAction(source, filename, sha1sum, size, target)

target_distribution_methods.register('scp', create_action)
