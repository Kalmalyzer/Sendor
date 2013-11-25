
Target = Backbone.Model.extend({
	idAttribute: "target_id"
});

Targets = Backbone.Collection.extend({
	model: Target,
	url: "../api/targets",

	parse: function(response) {
		return response.collection;
	}
});

StashedFile = Backbone.Model.extend({
	idAttribute: "file_id",
});

FileStash = Backbone.Collection.extend({
	model: StashedFile,
	url: "../api/file_stash",

	parse: function(response) {
		return response.collection;
	}
});

StashedFileView = Backbone.View.extend({
	tagName: "tr",

	template: _.template($('#StashedFileView-template').html()),

	events: {
		"click #delete": "deleteRequest",
		"click #distribute": "toggleDistribute",
		"click #distribute-submit": "distributeRequest",
		"click #toggle-all-targets": "toggleAllTargets"
	},	
	
	initialize: function(stashedFile, targets) {
		this.stashedFile = stashedFile;
		this.targets = targets;
		this.listenTo(this.stashedFile, "change", this.render);
		this.listenTo(this.targets, "change", this.render);
	},

	dataJSON: function() {
		return { stashed_file : this.stashedFile.toJSON(),
			targets : this.targets.toJSON() };
	},

	render: function() {
		this.$el.html(this.template(this.dataJSON()));
		return this;
	},
	
	deleteRequest: function() {
		$.ajax({ url: this.stashedFile.url() + '/delete',
			type: 'DELETE' });
	},

	toggleDistribute: function() {
		var distributeSection = this.$('#distribute-section');
		if (distributeSection.css('display') == 'none')
			distributeSection.css('display', '');
		else
			distributeSection.css('display', 'none');
	},
	
	distributeRequest: function(event) {
		_.each(this.$('input:checkbox'), function(targetObject) {
			if (targetObject.value != 'selectAll' && targetObject.checked)
			{
				var target_id = targetObject.value;
				$.ajax({ url: this.stashedFile.url() + '/distribute/' + target_id,
					type: 'POST' });
			}
		}, this);

		// Disable the "Distribute!" button for 3 seconds
		var submitButton = this.$('#distribute-submit');
		submitButton.prop('disabled', true);
		window.setTimeout(function() {
				submitButton.prop('disabled', false);
			}, 3000);
	},
	
	toggleAllTargets: function() {
		var checkAllTargets = $('#toggle-all-targets').prop('checked');
		var checkBoxes = $('input:checkbox');
		checkBoxes.prop('checked', checkAllTargets);
	}
});

var FileStashView = Backbone.View.extend({
	tagName: "table",
	className: "table table-bordered table-hover",

	initialize: function(fileStash, targets) {
		this.fileStash = fileStash;
		this.targets = targets;
		this.listenTo(this.fileStash, 'add remove reset', this.render);
		this.listenTo(this.targets, 'add remove reset', this.render);
	},

    render: function() {
		this.$el.empty();
		this.fileStash.each(function(stashedFile) {
			var stashedFileView = new StashedFileView(stashedFile, targets);
			stashedFileView.render();
			this.$el.append(stashedFileView.el);
			}, this);
		return this;
	},
});

var targets = new Targets();
targets.fetch({reset: true});
window.setInterval(function(){ targets.fetch(); }, 10000);

var fileStash = new FileStash();
fileStash.fetch({reset: true});
window.setInterval(function(){ fileStash.fetch(); }, 10000);

var fileStashView = new FileStashView(fileStash, targets);
$('#file_stash').html(fileStashView.el);
