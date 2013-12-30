'use strict';

var StashedFile = Backbone.Model.extend({
	idAttribute: 'file_id'
});

var FileStash = Backsync.Collection.extend({
	model: StashedFile,
	url: '/api/file_stash'
});

var StashedFileView = Backbone.View.extend({
	tagName: 'tr',

	template: _.template($('#StashedFileView-template').html()),

	events: {
		'click .delete-button': 'deleteRequest',
		'click .distribute-display-button': 'toggleDistribute',
	},	

	initialize: function(stashedFile, targets) {
		this.stashedFile = stashedFile;
		this.listenTo(this.stashedFile, 'change', this.render);
		
		this.base_class_remove = this.remove;
		this.remove = this.local_remove;
		this.targetsView = new TargetsView(targets, this.stashedFile.url());
	},

	local_remove: function() {
		this.targetsView.remove();
		this.base_class_remove();
	},
	
	render: function() {
		this.$el.html(this.template(this.stashedFile.toJSON()));
		this.$el.find('.distribute-section').append(this.targetsView.render().el);
		return this;
	},
	
	deleteRequest: function() {
		$.ajax({ url: this.stashedFile.url(),
			type: 'DELETE' });
	},

	toggleDistribute: function() {
		var distributeSection = this.$('.distribute-section');
		if (distributeSection.css('display') === 'none')
			distributeSection.css('display', '');
		else
			distributeSection.css('display', 'none');
	}
});

var FileStashView = Backbone.View.extend({
	tagName: 'table',
	className: 'table table-bordered table-hover',

	initialize: function(fileStash, targets) {
		this.fileStash = fileStash;
		this.targets = targets;
		this.listenTo(this.fileStash, 'add remove reset', this.render);
	},

    render: function() {
		this.$el.empty();
		this.fileStash.each(function(stashedFile) {
			var stashedFileView = new StashedFileView(stashedFile, this.targets);
			stashedFileView.render();
			this.$el.append(stashedFileView.el);
			}, this);
		return this;
	}
});
