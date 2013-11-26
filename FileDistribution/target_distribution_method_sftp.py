
import os.path

import target_distribution_methods

from actions import TestIfFileUpToDateOnTargetAction, SftpSendFileAction

def create_actions(source, filename, sha1sum, size, target):	
	return [TestIfFileUpToDateOnTargetAction(filename, sha1sum, target),
		SftpSendFileAction(source, filename, sha1sum, size, target)]

target_distribution_methods.register('sftp', create_actions)
