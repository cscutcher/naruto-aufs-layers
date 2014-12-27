# -*- coding: utf-8 -*-
"""
Simpler tests
"""
import logging
import tempfile
import unittest

from naruto import NarutoLayer, LayerNotFound

DEV_LOGGER = logging.getLogger(__name__)


class TestNaruto(unittest.TestCase):
    '''
    Broad tests for Naruto
    '''
    def setUp(self):
        self.root_naruto_dir = tempfile.TemporaryDirectory()
        self.inst = NarutoLayer.create(self.root_naruto_dir.name)

    def tearDown(self):
        self.inst.unmount_all()
        self.root_naruto_dir.cleanup()

    def test_naruto_mount(self):
        '''
        Test naruto creation and mount
        '''
        mount_path = tempfile.TemporaryDirectory()
        self.addCleanup(mount_path.cleanup)
        self.inst.mount(mount_path.name)

    def test_naruto_mount_child(self):
        '''
        Test naruto creation and mount with children
        '''
        child_mount_path = tempfile.TemporaryDirectory()
        self.addCleanup(child_mount_path.cleanup)

        child = self.inst.create_child()
        child.mount(child_mount_path.name)

        grandchild_mount_path = tempfile.TemporaryDirectory()
        self.addCleanup(grandchild_mount_path.cleanup)

        grandchild = child.create_child()
        grandchild.mount(grandchild_mount_path.name)

    def test_find_layer(self):
        '''
        Test finding a layer
        '''
        child = self.inst.create_child()
        grandchild = child.create_child()

        self.assertEqual(self.inst, grandchild.find_layer('root'))
        self.assertEqual(child, grandchild.find_layer('root^'))

    def test_find_layer_at_dest(self):
        '''
        Test finding a layer by a mounted path
        '''
        child_mount_path = tempfile.TemporaryDirectory()
        self.addCleanup(child_mount_path.cleanup)

        child = self.inst.create_child()
        child.mount(child_mount_path.name)

        grandchild_mount_path = tempfile.TemporaryDirectory()
        self.addCleanup(grandchild_mount_path.cleanup)

        grandchild = child.create_child()
        grandchild.mount(grandchild_mount_path.name)

        self.assertEqual(
            grandchild,
            NarutoLayer.find_layer_mounted_at_dest(grandchild_mount_path.name))

    def test_find_layer_at_dest_non_aufs(self):
        '''
        Test finding a layer by a mounted path when said path isn't aufs
        '''
        self.assertRaises(
            LayerNotFound,
            NarutoLayer.find_layer_mounted_at_dest,
            '/')
