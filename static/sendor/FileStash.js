
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

	events: {
		"click #delete": "deleteRequest"
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
	
	deleteRequest: function() {
		$.ajax({ url: this.model.url() + '/delete',
			type: 'DELETE' });
	}
});

var FileStashView = Backbone.View.extend({
	tagName: "table",
	className: "table table-bordered table-hover",

	initialize: function() {
		this.listenTo(this.collection, 'add remove reset', this.render);
	},

    render: function() {
		this.$el.empty();
		this.collection.each(function(stashedFile) {
			var stashedFileView = new StashedFileView({model: stashedFile});
			stashedFileView.render();
			this.$el.append(stashedFileView.el);
			}, this);
		return this;
	},
});

var fileStash = new FileStash();
var fileStashView = new FileStashView({collection: fileStash});
fileStash.fetch({reset: true});

$('#file_stash').html(fileStashView.el);

window.setInterval(function(){ fileStash.fetch(); }, 10000);
