
import datetime
import logging
import os.path

from flask import Blueprint, Response, render_template, redirect, request
from werkzeug import secure_filename

logger = logging.getLogger('main.ui')

def create_ui(file_stash, upload_folder):

	ui_app = Blueprint('ui', __name__)

	@ui_app.route('/')
	@ui_app.route('/index.html', methods = ['GET'])
	def index():
	
#		if request.args.get('cancel'):
#			g_sendor_queue.cancel_current_job()
	
		return render_template('index.html')

	@ui_app.route('/upload.html', methods = ['GET', 'POST'])
	def upload():
		if request.method == 'GET':
			return Response(render_template('upload_form.html'))

		elif request.method == 'POST':

			file = request.files['file']
			filename = secure_filename(file.filename)
			upload_file_full_path = os.path.join(upload_folder, filename)
			file.save(upload_file_full_path)

			file_stash.add(upload_folder, filename, datetime.datetime.utcnow())

			return redirect('index.html')

	logger.info("Created ui")

	return ui_app

