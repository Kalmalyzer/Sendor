'use strict';

var SendorTask = Backbone.Model.extend({
	idAttribute: "task_id",
	
	initialize: function() {
		this.set('show_log', false);
	}
});

var SendorTasks = Backsync.Collection.extend({
	model: SendorTask,
	url: "/api/tasks"
});

var SendorTaskView = Backbone.View.extend({
	tagName: "tr",

	template: _.template($('#SendorTaskView-template').html()),
	
	events: {
		"click .cancel-button": "cancelRequest",
		"click .toggle-log": "toggleLog"
	},

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
	},

	cancelRequest: function() {
		$.ajax({ url: this.model.url() + '/cancel',
			type: 'PUT' });
	},
	
	toggleLog: function() {
		this.model.set('show_log', !this.model.get('show_log'));
	}
});

var SendorTasksView = Backbone.View.extend({
	tagName: "table",
	className: "table table-striped",

	initialize: function() {
		this.taskViews = [];
		this.listenTo(this.collection, 'add remove reset', this.render);
	},

	clear: function() {
		this.$el.empty();
		_.each(this.taskViews, function(taskView) { taskView.remove(); });
		this.taskViews = [];
	},
	
    render: function() {
		this.clear();

		this.collection.each(function(task) {
				var taskView = new SendorTaskView({model: task});
				this.taskViews.push(taskView);
				taskView.render();
				this.$el.prepend(taskView.el);
			}, this);
		return this;
	}
});
