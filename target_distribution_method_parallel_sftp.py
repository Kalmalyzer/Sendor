
import os.path

import target_distribution_methods

from actions import ParallelSftpSendFileAction

def create_action(source, target):	
	return ParallelSftpSendFileAction(source, target)

target_distribution_methods.register('parallel_sftp', create_action)
