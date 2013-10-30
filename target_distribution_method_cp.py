
import os.path

import target_distribution_methods

from actions import CopyFileAction

def create_action(source, filename, target):	
	target_filename = os.path.join(target['directory'], filename)
	return CopyFileAction(source, target_filename)

target_distribution_methods.register('cp', create_action)
