'use strict';

describe("SendorTaskView & SendorTasksView", function() {

	describe("SendorTaskView", function() {
		
		beforeEach(function() {
			var sendorTask = new SendorTask({task_id: 5 });
			this.sendorTaskView = new SendorTaskView({model: sendorTask});
		});

		describe("Instantiation", function() {
			it("Should create a table row", function() {
				expect(this.sendorTaskView.el.nodeName).toEqual('TR');
			});
		});
	});

	describe("SendorTasksView", function() {
		
		describe("Instantiation", function() {
		
			beforeEach(function() {
				this.sendorTasks = new SendorTasks();
				this.sendorTasksView = new SendorTasksView({collection: this.sendorTasks});
			});

			it("Should create a table", function() {
				expect(this.sendorTasksView.el.nodeName).toEqual('TABLE');
			});
		});
		
		describe("Rendering", function() {

			beforeEach(function() {
				this.task1 = new SendorTask({task_id: 1, is_cancelable: true, completion_ratio: 0, duration: 0, description: "Task 1", log: "", state: 'not_started'});
				this.task2 = new SendorTask({task_id: 2, is_cancelable: true, completion_ratio: 0, duration: 0, description: "Task 2", log: "", state: 'not_started'});
				this.task3 = new SendorTask({task_id: 3, is_cancelable: true, completion_ratio: 0, duration: 0, description: "Task 3", log: "", state: 'not_started'});
				this.sendorTasks = new SendorTasks([this.task1, this.task2, this.task3]);
				this.sendorTasksView = new SendorTasksView({collection: this.sendorTasks});

				this.sendorTaskView_constructor_spy = sinon.spy(window, 'SendorTaskView');
			});

			afterEach(function() {
				this.sendorTaskView_constructor_spy.restore();
			});

			it("Should create one view object & DOM element per element in the collection", function() {
				expect(this.sendorTaskView_constructor_spy.callCount).toEqual(0);
				this.sendorTasksView.render();
				expect(this.sendorTasksView.$el.find('tr').length).toEqual(this.sendorTasks.models.length);
				expect(this.sendorTaskView_constructor_spy.callCount).toEqual(this.sendorTasks.models.length);
			});

			it("Re-rendering should destroy and recreate all view objects & DOM elements", function() {
				expect(this.sendorTaskView_constructor_spy.callCount).toEqual(0);
				this.sendorTasksView.render();
				expect(this.sendorTasksView.$el.find('tr').length).toEqual(this.sendorTasks.models.length);
				expect(this.sendorTaskView_constructor_spy.callCount).toEqual(1 * this.sendorTasks.models.length);
				this.sendorTasksView.render();
				this.sendorTasksView.render();
				expect(this.sendorTasksView.$el.find('tr').length).toEqual(this.sendorTasks.models.length);
				expect(this.sendorTaskView_constructor_spy.callCount).toEqual(3 * this.sendorTasks.models.length);
			});
		});
	});
});
