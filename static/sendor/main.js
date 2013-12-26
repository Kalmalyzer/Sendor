'use strict';

var targets = new Targets();
targets.fetch({reset: true});
//window.setInterval(function(){ targets.fetch(); }, 10000);

var fileStash = new FileStash();
fileStash.fetch({reset: true});
//window.setInterval(function(){ fileStash.fetch(); }, 10000);

var fileStashView = new FileStashView(fileStash, targets);
$('#file_stash').html(fileStashView.el);




var tasks = new SendorTasks();
var tasksView = new SendorTasksView({collection: tasks});
tasks.fetch({reset: true});

$('#tasks').html(tasksView.el);

//window.setInterval(function(){ tasks.fetch(); }, 10000);
