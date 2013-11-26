import os.path
import logging
import logging.handlers

def initialize_logger(settings):
	filename = 'activity.log'

	if settings['output'] == 'file':
		file_handler = logging.handlers.TimedRotatingFileHandler(
			filename=os.path.join(settings['log_folder'], filename),
			when='midnight',
			utc=True)
		formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
		file_handler.setFormatter(formatter)

		root_logger = logging.getLogger()
		root_logger.setLevel(logging.INFO)
		root_logger.addHandler(file_handler)
