// This is a script for running Jasmine testsuites in PhantomJS.
// It will output the test results to the console instead of displaying it on a webpage.
//
// It is based on Joshua Carver's "phantom-jasmine" project: https://github.com/jcarver989/phantom-jasmine
// however this version is designed to work with Jasmine 2.x's native ConsoleReporter.
//
// Usage: phantomjs <path to this file> <path to Jasmine SpecRunner.html file>
//

'use strict';

var system = require('system');

if (phantom.args.length == 0)
{
	console.log("Need a url as the argument");
	phantom.exit(1);
}

var page = new WebPage();

page.onConsoleMessage = function(msg) {
	system.stdout.write(msg);

	// Check for test termination message
	var prefixString = 'ConsoleReporter finished ';
	if (msg.indexOf(prefixString) == 0)
	{
		// Determine test success/failure by parsing termination message
		if (msg.indexOf('success') != -1)
			phantom.exit(0);
		else if (msg.indexOf('fail') != -1)
			phantom.exit(2);
		else
			phantom.exit(1);
	}
};

// Open page and execute test suite

var url = phantom.args[0];

console.log("Executing Jasmine test suite");

page.open(url, function(status) {
	if (status != "success")
	{
		console.log("can't load SpecRunner file " + url);
		console.log(status);
		phantom.exit(1);
	}
});

// Now we wait until onConsoleMessage reads the termination signal from the log. 
