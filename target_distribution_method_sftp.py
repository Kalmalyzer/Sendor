
import os.path

import target_distribution_methods

from actions import SftpSendFileAction

def create_action(source, target):	
	return SftpSendFileAction(source, target)

target_distribution_methods.register('sftp', create_action)
