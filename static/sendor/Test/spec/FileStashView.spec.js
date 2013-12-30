'use strict';

describe("StashedFileView & FileStashView", function() {

	describe("StashedFileView", function() {
		
		beforeEach(function() {
			this.stashedFile = new StashedFile({file_id: 'abcd', is_deletable: true, original_filename: "", size: 0, timestamp: ""});
			this.targets = new Targets();

			this.fileStash = new FileStash(this.stashedFile);
			this.stashedFileView_constructor_spy = sinon.spy(window, 'StashedFileView');
			this.targetsView_constructor_spy = sinon.spy(window, 'TargetsView');
		});
		
		afterEach(function() {
			this.stashedFileView_constructor_spy.restore();
			this.targetsView_constructor_spy.restore();
		});

		describe("Instantiation and removal", function() {
			it("Should create a table row", function() {
				var stashedFileView = new StashedFileView(this.stashedFile, this.targets);
				expect(stashedFileView.el.nodeName).toEqual('TR');
			});

			it("Should create both a StashedFileView and a TargetsView", function() {
				var stashedFileView = new StashedFileView(this.stashedFile, this.targets);
				expect(this.stashedFileView_constructor_spy.calledOnce).toBe(true);
				expect(this.targetsView_constructor_spy.calledOnce).toBe(true);
			});
			
			it("Removal calls should be chained on to the base class and also the TargetsView", function() {
				var stashedFileView = new StashedFileView(this.stashedFile, this.targets);
				sinon.spy(stashedFileView, 'remove');
				sinon.spy(stashedFileView, 'base_class_remove');
				sinon.spy(stashedFileView.targetsView, 'remove');

				stashedFileView.remove();
				expect(stashedFileView.remove.calledOnce).toBe(true);
				expect(stashedFileView.base_class_remove.calledOnce).toBe(true);
				expect(stashedFileView.targetsView.remove.calledOnce).toBe(true);
			});
		});
	});

	describe("FileStashView", function() {
		
		describe("Instantiation", function() {
		
			beforeEach(function() {
				this.fileStash = new FileStash();
				this.targets = new Targets();
				this.fileStashView = new FileStashView(this.fileStash, this.targets);
			});

			it("Should create a table", function() {
				expect(this.fileStashView.el.nodeName).toEqual('TABLE');
			});
		});
		
		describe("Rendering", function() {

			beforeEach(function() {
				this.file1 = new StashedFile({file_id: '1', is_deletable: true, original_filename: "", size: 0, timestamp: ""});
				this.file2 = new StashedFile({file_id: '2', is_deletable: true, original_filename: "", size: 0, timestamp: ""});
				this.target1 = new Target({target_id: '101', name: 'Target 1'});
				this.target2 = new Target({target_id: '102', name: 'Target 2'});
				this.targets = new Targets([this.target1, this.target2]);
				this.fileStash = new FileStash([this.file1, this.file2]);
				this.fileStashView = new FileStashView(this.fileStash, this.targets);

				this.stashedFileView_constructor_spy = sinon.spy(window, 'StashedFileView');
				this.targetsView_constructor_spy = sinon.spy(window, 'TargetsView');
			});

			afterEach(function() {
				this.stashedFileView_constructor_spy.restore();
				this.targetsView_constructor_spy.restore();
			});

			it("Should create one StashedFile view object & DOM element per element in the collection - and the Targets subview for each", function() {
				expect(this.stashedFileView_constructor_spy.callCount).toEqual(0);
				expect(this.targetsView_constructor_spy.callCount).toEqual(0);
				this.fileStashView.render();
				expect(this.fileStashView.$el.find('tr').length).toEqual(this.fileStash.models.length);
				expect(this.stashedFileView_constructor_spy.callCount).toEqual(this.fileStash.models.length);
				expect(this.targetsView_constructor_spy.callCount).toEqual(this.fileStash.models.length);
			});

			it("Re-rendering should destroy and recreate all view objects & DOM elements", function() {
				expect(this.stashedFileView_constructor_spy.callCount).toEqual(0);
				expect(this.targetsView_constructor_spy.callCount).toEqual(0);
				this.fileStashView.render();
				expect(this.fileStashView.$el.find('tr').length).toEqual(this.fileStash.models.length);
				expect(this.stashedFileView_constructor_spy.callCount).toEqual(1 * this.fileStash.models.length);
				expect(this.targetsView_constructor_spy.callCount).toEqual(1 * this.fileStash.models.length);
				this.fileStashView.render();
				this.fileStashView.render();
				expect(this.fileStashView.$el.find('tr').length).toEqual(this.fileStash.models.length);
				expect(this.stashedFileView_constructor_spy.callCount).toEqual(3 * this.fileStash.models.length);
				expect(this.targetsView_constructor_spy.callCount).toEqual(3 * this.fileStash.models.length);
			});
			
		});

		describe("Events", function() {
			beforeEach(function() {
				this.file1 = new StashedFile({file_id: '1', is_deletable: true, original_filename: "", size: 0, timestamp: ""});
				this.file2 = new StashedFile({file_id: '2', is_deletable: true, original_filename: "", size: 0, timestamp: ""});
				this.target1 = new Target({target_id: '101', name: 'Target 1'});
				this.target2 = new Target({target_id: '102', name: 'Target 2'});
				this.targets = new Targets([this.target1, this.target2]);
				this.fileStash = new FileStash([this.file1, this.file2]);
				this.fileStashView = new FileStashView(this.fileStash, this.targets);

				this.stashedFileView_constructor_spy = sinon.spy(window, 'StashedFileView');
				this.targetsView_constructor_spy = sinon.spy(window, 'TargetsView');
			});

			afterEach(function() {
				this.stashedFileView_constructor_spy.restore();
				this.targetsView_constructor_spy.restore();
			});

			it("Should hide/show the targets when clicking the 'Distribute' button for one file", function() {
				
				this.fileStashView.render();
				var distributeSection = this.fileStashView.$el.find('tr[file_id="1"] .distribute-section');
				var distributeButton = this.fileStashView.$el.find('tr[file_id="1"] .distribute-display-button');

				expect(distributeSection).toHaveCss({display: 'none'});
				distributeButton.click();
				expect(distributeSection).not.toHaveCss({display: 'none'});
				distributeButton.click();
				expect(distributeSection).toHaveCss({display: 'none'});
			});
		});
	});
});
