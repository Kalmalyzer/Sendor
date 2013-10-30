
import os.path

import target_distribution_methods

from actions import ParallelSftpSendFileAction

def create_action(source, filename, target):	
	return ParallelSftpSendFileAction(source, filename, target)

target_distribution_methods.register('parallel_sftp', create_action)
