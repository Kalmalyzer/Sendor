'use strict';

describe("TargetsView", function() {

	beforeEach(function() {
		this.target1 = new Target({target_id: '1', name: "Target 1"});
		this.target2 = new StashedFile({target_id: '2', name: "Target 2"});
		this.targets = new Targets([this.target1, this.target2]);
		this.targetsView = new TargetsView(this.targets);

		this.targetsView_constructor_spy = sinon.spy(window, 'TargetsView');
	});
		
	afterEach(function() {
		this.targetsView_constructor_spy.restore();
	});

	describe("Instantiation", function() {
		it("Should create a table", function() {
			expect(this.targetsView.el.nodeName).toEqual('TABLE');
		});
	});

	describe("Rendering", function() {
		it("Should create one checkbox per element in the collection, plus the toggleAll-checkbox", function() {
			this.targetsView.render();
			expect(this.targetsView.$el.find('.checkbox').length).toEqual(this.targetsView.targets.length + 1);
		});
	});
});
