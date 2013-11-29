'use strict';

var SendorTask = Backbone.Model.extend({
	idAttribute: "task_id"
});

var SendorTasks = Backsync.Collection.extend({
	model: SendorTask,
	url: "/api/tasks"
});

var SendorTaskView = Backbone.View.extend({
	tagName: "tr",

	template: _.template($('#SendorTaskView-template').html()),
	
	initialize: function() {
		this.listenTo(this.model, "change", this.change);
	 },

	render: function() {
		this.$el.html(this.template(this.model.toJSON()));
		return this;
	},

	change: function() {
		this.$el.html(this.template(this.model.toJSON()));
		return this;
	}
});

var SendorTasksView = Backbone.View.extend({
	tagName: "table",
	className: "table table-striped",

	initialize: function() {
		this.listenTo(this.collection, 'add remove reset', this.render);
	},

    render: function() {
		this.$el.empty();
		this.collection.each(function(task) {
				var taskView = new SendorTaskView({model: task});
				taskView.render();
				this.$el.append(taskView.el);
			}, this);
		return this;
	}
});


var tasks = new SendorTasks();
var tasksView = new SendorTasksView({collection: tasks});
tasks.fetch({reset: true});

$('#tasks').html(tasksView.el);

//window.setInterval(function(){ tasks.fetch(); }, 10000);
