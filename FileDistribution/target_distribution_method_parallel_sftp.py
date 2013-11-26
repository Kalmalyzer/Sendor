
import os.path

import target_distribution_methods

from actions import TestIfFileUpToDateOnTargetAction, ParallelSftpSendFileAction

def create_actions(source, filename, sha1sum, size, target):	
	return [TestIfFileUpToDateOnTargetAction(filename, sha1sum, target),
		ParallelSftpSendFileAction(source, filename, sha1sum, size, target)]

target_distribution_methods.register('parallel_sftp', create_actions)
