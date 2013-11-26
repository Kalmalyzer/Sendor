import json
import sys

def load_config(host_config_filename, targets_config_filename):
	config = {}
	with open(host_config_filename) as file:
		config = json.load(file)
	with open(targets_config_filename) as file:
		config['targets'] = json.load(file)
	return config
