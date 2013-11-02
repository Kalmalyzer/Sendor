
target_distribution_methods = {}
	
def register(target_distribution_method_name, target_distribution_method):
	target_distribution_methods[target_distribution_method_name] = target_distribution_method

def create_action(source, target):
	return target_distribution_methods[target['distribution_method']](source, target)
