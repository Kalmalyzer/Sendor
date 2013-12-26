'use strict';

describe("Target & Targets", function() {

	describe("Target", function() {
		
		beforeEach(function() {
			this.target = new Target();
		});
		
		it("should have a predefined custom id-attribute", function() {
			expect(this.target.idAttribute).toEqual('target_id');
		});
	});

	describe("Targets", function() {
		
		beforeEach(function() {
			this.targets = new Targets();
		});
		
		it("should have a predefined model", function() {
			expect(this.targets.model).toEqual(Target);
		});
		
		it("should have a predefined resource URL", function() {
			expect(this.targets.url).toEqual('/api/targets');
		});
	});
});
