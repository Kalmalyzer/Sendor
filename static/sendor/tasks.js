
Task = Backbone.Model.extend({
	idAttribute: "task_id",

	initialize: function() {
	}
});

Tasks = Backbone.Collection.extend({
	model: Task,
	url: "tasks",

	initialize: function() {
	},

	parse: function(response) {
		return response.collection;
	}
});

TaskView = Backbone.View.extend({
	tagName: "tr",

	template: _.template($('#taskview-template').html()),
	
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

var TasksView = Backbone.View.extend({
	tagName: "table",
	className: "table table-striped",

	initialize: function() {
		this.listenTo(this.collection, 'reset', this.render);
		this.listenTo(this.collection, 'add', this.add);
		this.listenTo(this.collection, 'remove', this.remove);
	},

	add: function(task) {
		var taskView = new TaskView({model: task});
		taskView.render();
		this.$el.append(taskView.el);
		return this;
	},

	remove: function(task) {
		// TODO: implement removal of element from DOM tree
		console.log("Not yet implemented");
		debugger;
	},

    render: function() {
		this.$el.empty();
		this.collection.each(function(task) {
				var taskView = new TaskView({model: task});
				taskView.render();
				this.$el.append(taskView.el);
			}, this);
		return this;
	}
});


var tasks = new Tasks();
var tasksView = new TasksView({collection: tasks});
tasks.fetch({reset: true});

$('#tasks').html(tasksView.el);

window.setInterval(function(){ tasks.fetch(); }, 10000);
