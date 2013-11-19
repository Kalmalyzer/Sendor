
StashedFile = Backbone.Model.extend({
	idAttribute: "file_id",

	initialize: function() {
	}
});

FileStash = Backbone.Collection.extend({
	model: StashedFile,
	url: "../api/file_stash",

	initialize: function() {
	},

	parse: function(response) {
		return response.collection;
	}
});

StashedFileView = Backbone.View.extend({
	tagName: "tr",

	template: _.template($('#StashedFileView-template').html()),
	
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

var FileStashView = Backbone.View.extend({
	tagName: "table",
	className: "table table-bordered table-hover",

	initialize: function() {
		this.listenTo(this.collection, 'reset', this.render);
		this.listenTo(this.collection, 'add', this.add);
		this.listenTo(this.collection, 'remove', this.remove);
	},

	add: function(stashedFile) {
		var stashedFileView = new StashedFileView({model: stashedFile});
		stashedFileView.render();
		this.$el.append(stashedFileView.el);
		return this;
	},

	remove: function(stashedFile) {
		// TODO: implement removal of element from DOM tree
		console.log("Not yet implemented");
		debugger;
	},

    render: function() {
		this.$el.empty();
		this.collection.each(function(stashedFile) {
				var stashedFileView = new StashedFileView({model: stashedFile});
				stashedFileView.render();
				this.$el.append(stashedFileView.el);
			}, this);
		return this;
	}
});

var fileStash = new FileStash();
var fileStashView = new FileStashView({collection: fileStash});
fileStash.fetch({reset: true});

$('#file_stash').html(fileStashView.el);

window.setInterval(function(){ fileStash.fetch(); }, 10000);
