
import os.path

import target_distribution_methods

from actions import SftpSendFileAction

def create_action(source, filename, sha1sum, size, target):	
	return SftpSendFileAction(source, filename, sha1sum, size, target)

target_distribution_methods.register('sftp', create_action)
