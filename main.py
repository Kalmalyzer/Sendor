
import datetime
import json
import logging
import logging.handlers
import sys
import os

import flask.config
from flask import Flask
from flask import Blueprint, Response, redirect, url_for, render_template, request
from werkzeug import secure_filename

from SendorJob import SendorJob
from SendorQueue import SendorQueue
from FileStash import FileStash
from Targets import Targets

from tasks import DistributeFileTask

logger = logging.getLogger('main')

g_sendor_queue = None

g_file_stash = None
g_targets = None

g_config = {}

class SendorDistributionJob(SendorJob):

	def __init__(self, stashed_file, tasks):
		super(SendorDistributionJob, self).__init__(tasks)
		self.stashed_file = stashed_file

	def completed(self):
		g_file_stash.unlock(self.stashed_file)

		
def create_ui(upload_folder):

	ui_app = Blueprint('ui', __name__)

	@ui_app.route('/')
	@ui_app.route('/index.html', methods = ['GET'])
	def index():
	
		if request.args.get('cancel'):
			g_sendor_queue.cancel_current_job()

		file_stash = sorted(g_file_stash.list(), cmp = lambda x, y: cmp(x.timestamp, y.timestamp))
		latest_uploaded_file = []
		if len(file_stash) != 0:
			latest_uploaded_file = [file_stash[-1].to_json()]
	
		pending_jobs = []
		for job in reversed(list(g_sendor_queue.pending_jobs.queue)):
			pending_jobs.append(job.progress())

		current_job = None
		if g_sendor_queue.worker.current_job:
			current_job = g_sendor_queue.worker.current_job.progress()

		past_jobs = []
		for job in reversed(list(g_sendor_queue.past_jobs.queue)):
			past_jobs.append(job.progress())

		return render_template('index.html',
			file_stash = latest_uploaded_file,
			pending_jobs = pending_jobs,
			current_job = current_job,
			past_jobs = past_jobs)

	@ui_app.route('/file_stash.html', methods = ['GET'])
	def file_stash():

		if request.args.get('clear'):
			g_sendor_queue.cancel_current_job()
			g_file_stash.remove_all_unlocked_files()
	
		file_stash = sorted(g_file_stash.list(), cmp = lambda x, y: cmp(x.timestamp, y.timestamp))
		file_stash_contents = []
		for file in file_stash:
			file_stash_contents.append(file.to_json())
	
		return render_template('file_stash.html',
			file_stash = file_stash_contents)

	@ui_app.route('/upload.html', methods = ['GET', 'POST'])
	def upload():
		if request.method == 'GET':
			return Response(render_template('upload_form.html'))

		elif request.method == 'POST':

			file = request.files['file']
			filename = secure_filename(file.filename)
			upload_file_full_path = os.path.join(upload_folder, filename)
			file.save(upload_file_full_path)

			g_file_stash.add(upload_folder, filename, datetime.datetime.utcnow())

			return redirect('index.html')

	@ui_app.route('/distribute.html/<id>', methods = ['GET', 'POST'])
	def distribute(id):
		if request.method == 'GET':
			file_stash = [g_file_stash.get(id).to_json()]
		
			return Response(render_template('distribute.html',
							file_stash = file_stash,
							targets = g_targets.get_targets()))

		elif request.method == 'POST':

			target_ids = request.form.getlist('target')
			id = request.form.get('file')
			stashed_file = g_file_stash.lock(id)

			distribute_file_tasks = []
			for id in target_ids:
				distribute_file_task = DistributeFileTask(stashed_file.original_filename, id)
				distribute_file_actions = g_targets.create_distribution_actions(stashed_file.full_path_filename, stashed_file.original_filename, id)
				distribute_file_task.actions.extend(distribute_file_actions)
				distribute_file_tasks.append(distribute_file_task)

			job = SendorDistributionJob(stashed_file, distribute_file_tasks)
			g_sendor_queue.add(job)

			return redirect('index.html')

	logger.info("Created ui")

	return ui_app

def create_api():

	api_app = Blueprint('api', __name__)
	@api_app.route('/file_stash/<file_id>/delete', methods = ['POST'])
	def file_stash_delete(file_id):
		g_file_stash.remove(file_id)
		return ""
	
	return api_app

	
def load_config(host_config_filename, targets_config_filename):
	global g_config
	with open(host_config_filename) as file:
		g_config = json.load(file)
	with open(targets_config_filename) as file:
		g_config['targets'] = json.load(file)

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

def main(host_config_filename, targets_config_filename):
	global g_sendor_queue
	global g_file_stash
	global g_targets

	load_config(host_config_filename, targets_config_filename)

	initialize_logger(g_config['logging'])
	
	host = g_config['host']
	port = int(g_config['port'])
	upload_folder = g_config['upload_folder']
	file_stash_folder = g_config['file_stash_folder']
	queue_folder = g_config['queue_folder']
	num_distribution_processes = int(g_config['num_distribution_processes'])

	root = Flask(__name__)
	root.config['host_description'] = g_config['host_description']

	ui_app = create_ui(upload_folder)
	root.register_blueprint(url_prefix = '/ui', blueprint = ui_app)
	api_app = create_api()
	root.register_blueprint(url_prefix = '/api', blueprint = api_app)

	@root.route('/')
	@root.route('/index.html')
	def index():
		return redirect('ui')

	g_sendor_queue = SendorQueue(num_distribution_processes, queue_folder)
	g_file_stash = FileStash(file_stash_folder)
	g_targets = Targets(g_config['targets'])

	logger.info("Starting wsgi server")


	root.run(host = host, port = port, debug = True)


if __name__ == '__main__':
	
	if len(sys.argv) != 3:
		print "Usage: main.py <host config> <targets config>"
	else:
		main(host_config_filename = sys.argv[1], targets_config_filename = sys.argv[2])
