'use strict';

describe("StashedFile & FileStash", function() {

	describe("StashedFile", function() {
		
		beforeEach(function() {
			this.stashedFile = new StashedFile();
		});
		
		it("should have a predefined custom id-attribute", function() {
			expect(this.stashedFile.idAttribute).toEqual('file_id');
		});
	});

	describe("FileStash", function() {
		
		beforeEach(function() {
			this.fileStash = new FileStash();
		});
		
		it("should have a predefined model", function() {
			expect(this.fileStash.model).toEqual(StashedFile);
		});
		
		it("should have a predefined resource URL", function() {
			expect(this.fileStash.url).toEqual('/api/file_stash');
		});
	});
});
