'use strict';

describe("SendorTask & SendorTasks", function() {

	describe("SendorTask", function() {
		
		beforeEach(function() {
			this.sendorTask = new SendorTask();
		});
		
		it("should have a predefined custom id-attribute", function() {
			expect(this.sendorTask.idAttribute).toEqual('task_id');
		});
	});

	describe("SendorTasks", function() {
		
		beforeEach(function() {
			this.sendorTasks = new SendorTasks();
		});
		
		it("should have a predefined model", function() {
			expect(this.sendorTasks.model).toEqual(SendorTask);
		});
		
		it("should have a predefined resource URL", function() {
			expect(this.sendorTasks.url).toEqual('/api/tasks');
		});
	});
});
