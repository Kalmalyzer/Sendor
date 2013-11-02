
import os.path

import target_distribution_methods

from actions import CopyFileAction

def create_action(source, target):	
	target_filename = os.path.join(target['directory'], source.original_filename)
	return CopyFileAction(source, target_filename)

target_distribution_methods.register('cp', create_action)
