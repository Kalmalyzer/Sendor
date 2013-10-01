
import os
import unittest
import time

import fabric.api

from fabric.api import local

from SendorQueue import SendorTask

class FabricTask(SendorTask):
    
    def fabric_local(self, command):
        with fabric.api.settings(warn_only = True):
            result = local(command, capture = True)
            self.append_details(command)
            self.append_details(result)
            self.append_details(result.stderr)
            if result.failed:
                raise Exception("Fabric command failed")

class CopyFileTask(FabricTask):

    def __init__(self, source, target):
        super(CopyFileTask, self).__init__()
        self.source = source
        self.target = target

    def run(self):
        self.fabric_local('cp ' + self.source + ' ' + self.target)

    def string_description(self):
        return "Copy file " + self.source + " to " + self.target

class UploadFileTask(SendorTask):

    def __init__(self, source):
        super(UploadFileTask, self).__init__()
        self.source = source

    def run(self):
        pass

    def string_description(self):
        return "Upload file " + self.source

class CopyFileTaskUnitTest(unittest.TestCase):

    def setUp(self):
        local('mkdir unittest')
        local('echo abc123 > unittest/source')

    def test_copy_file_task(self):

        self.assertFalse(os.path.exists('unittest/target'))
        task = CopyFileTask('unittest/source', 'unittest/target')
        task.run()
        self.assertTrue(os.path.exists('unittest/target'))

    def tearDown(self):
        local('rm -rf unittest')

if __name__ == '__main__':
    unittest.main()
