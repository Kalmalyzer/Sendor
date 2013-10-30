
import os.path

import target_distribution_methods

from actions import SftpSendFileAction

def create_action(source, filename, target):	
	return SftpSendFileAction(source, filename, target)

target_distribution_methods.register('sftp', create_action)
