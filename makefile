
tests : frontend_tests backend_tests

frontend_tests :
	phantomjs static/phantom-jasmine/run_jasmine_test.js static/sendor/Test/SpecRunner.html

backend_tests :
	python -m unittest discover . '*.py'
