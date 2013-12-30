'use strict';

var Target = Backbone.Model.extend({
	idAttribute: 'target_id'
});

var Targets = Backsync.Collection.extend({
	model: Target,
	url: '/api/targets'
});

var TargetsView = Backbone.View.extend({
	tagName: 'table',

	template: _.template($('#TargetsView-template').html()),

	events: {
		'click .toggle-all-targets-button': 'toggleAllTargets',
		'click .distribute-submit-button': 'distributeRequest'
	},	

	initialize: function(targets, stashedFileUrl) {
		this.stashedFileUrl = stashedFileUrl;
		this.targets = targets;
		this.listenTo(this.targets, 'add remove reset change', this.render);
	},

    render: function() {
		this.$el.html(this.template({targets: this.targets.toJSON()}));
		return this;
	},

	distributeRequest: function() {
		_.each(this.$('input:checkbox'), function(targetObject) {
			if (targetObject.value !== 'selectAll' && targetObject.checked)
			{
				var target_id = targetObject.value;
				$.ajax({ url: this.stashedFileUrl + '/distribute/' + target_id,
					type: 'POST' });
			}
		}, this);

		// Disable the "Distribute!" button for 3 seconds
		var submitButton = this.$('.distribute-submit-button');
		submitButton.prop('disabled', true);
		window.setTimeout(function() {
				submitButton.prop('disabled', false);
			}, 3000);
	},
	
	toggleAllTargets: function() {
		var checkAllTargets = $('.toggle-all-targets-button').prop('checked');
		var checkBoxes = $('input:checkbox');
		checkBoxes.prop('checked', checkAllTargets);
	}
});
