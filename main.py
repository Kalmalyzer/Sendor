
import logging
import sys

import tornado.wsgi
import tornado.web
import tornado.ioloop

from sockjs.tornado import SockJSRouter, SockJSConnection

from flask import Flask
from flask import redirect
from werkzeug import secure_filename

from FileDistribution.SendorQueue import SendorQueue
from FileDistribution.FileStash import FileStash
from FileDistribution.Targets import Targets

import FileDistribution.rest_api
import FileDistribution.backsync_api
import ui
import application_config
import application_logger

from backsync.router import BacksyncModelRouter

logger = logging.getLogger('main')

def main(host_config_filename, targets_config_filename):

	config = application_config.load_config(host_config_filename, targets_config_filename)

	application_logger.initialize_logger(config['logging'])
	
	host = config['host']
	port = int(config['port'])
	upload_folder = config['upload_folder']
	file_stash_folder = config['file_stash_folder']
	queue_folder = config['queue_folder']
	num_distribution_processes = int(config['num_distribution_processes'])
	max_file_age_days = int(config['max_file_age_days'])
	max_file_age_check_interval_seconds = int(config['max_file_age_check_interval_seconds'])
	max_task_execution_time_seconds = int(config['max_task_execution_time_seconds'])
	max_task_finalization_time_seconds = int(config['max_task_finalization_time_seconds'])

	root = Flask(__name__)
	root.config['host_description'] = config['host_description']
	root.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1

	sendor_queue = SendorQueue(num_distribution_processes, queue_folder, max_task_execution_time_seconds, max_task_finalization_time_seconds)
	file_stash = FileStash(file_stash_folder, max_file_age_days, max_file_age_check_interval_seconds)
	targets = Targets(config['targets'])

	ui_app = ui.create_ui(file_stash, upload_folder)
	root.register_blueprint(url_prefix = '/ui', blueprint = ui_app)
	rest_api_app = FileDistribution.rest_api.create_rest_api(sendor_queue, targets, file_stash)
	root.register_blueprint(url_prefix = '/api', blueprint = rest_api_app)

	FileDistribution.backsync_api.create_backsync_api(sendor_queue, targets, file_stash)
	
	@root.route('/')
	@root.route('/index.html')
	def index():
		return redirect('ui')

	logger.info("Starting wsgi server")

	wsgi_root = tornado.wsgi.WSGIContainer(root)

	backsyncRouter = SockJSRouter(BacksyncModelRouter, '/backsync') 

	handlers = []
	backsyncRouter.apply_routes(handlers)
	handlers.extend([(r".*", tornado.web.FallbackHandler, dict(fallback=wsgi_root))])
	
	application = tornado.web.Application(handlers)
	
	application.listen(port)
	tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
	
	if len(sys.argv) != 3:
		print "Usage: main.py <host config> <targets config>"
	else:
		main(host_config_filename = sys.argv[1], targets_config_filename = sys.argv[2])
