# Copyright 2014 Kevin L. Mitchell
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import unittest

import mock

from fstree import cacheprop


class TestClass(object):
    def __init__(self):
        self.calls = []

    @cacheprop.cached_property
    def simple(self):
        self.calls.append(('simple',))
        return 'simple'

    @cacheprop.cached_property('a', 'b')
    def under_a_b(self):
        self.calls.append(('under_a_b', self.a, self.b))
        return 'under_a_b: %s, %s' % (self.a, self.b)

    @cacheprop.cached_property('a', 'b', base='c')
    def under_ca_cb(self):
        self.calls.append(('under_ca_cb', self.c.a, self.c.b))
        return 'under_ca_cb: %s, %s' % (self.c.a, self.c.b)


class CachedPropertyFunctionTest(unittest.TestCase):
    def test_simple(self):
        obj = TestClass()

        self.assertEqual(obj.simple, 'simple')
        self.assertEqual(obj.simple, 'simple')
        self.assertEqual(obj.calls, [('simple',)])
        self.assertEqual(obj._simple, 'simple')
        self.assertEqual(obj.__cache_control__, {'simple': {}})

    def test_under_a_b(self):
        obj = TestClass()
        obj.a = 1
        obj.b = 2

        self.assertEqual(obj.under_a_b, 'under_a_b: 1, 2')
        self.assertEqual(obj.under_a_b, 'under_a_b: 1, 2')
        self.assertEqual(obj.calls, [('under_a_b', 1, 2)])
        self.assertEqual(obj._under_a_b, 'under_a_b: 1, 2')
        self.assertEqual(obj.__cache_control__,
                         {'under_a_b': {'a': 1, 'b': 2}})

        obj.calls = []
        obj.a = 2
        obj.b = 4

        self.assertEqual(obj.under_a_b, 'under_a_b: 2, 4')
        self.assertEqual(obj.under_a_b, 'under_a_b: 2, 4')
        self.assertEqual(obj.calls, [('under_a_b', 2, 4)])
        self.assertEqual(obj._under_a_b, 'under_a_b: 2, 4')
        self.assertEqual(obj.__cache_control__,
                         {'under_a_b': {'a': 2, 'b': 4}})

    def test_under_ca_cb(self):
        control = mock.Mock(a=1, b=2)

        obj = TestClass()
        obj.c = control

        self.assertEqual(obj.under_ca_cb, 'under_ca_cb: 1, 2')
        self.assertEqual(obj.under_ca_cb, 'under_ca_cb: 1, 2')
        self.assertEqual(obj.calls, [('under_ca_cb', 1, 2)])
        self.assertEqual(obj._under_ca_cb, 'under_ca_cb: 1, 2')
        self.assertEqual(obj.__cache_control__,
                         {'under_ca_cb': {'a': 1, 'b': 2}})

        obj.calls = []
        control.a = 2
        control.b = 4

        self.assertEqual(obj.under_ca_cb, 'under_ca_cb: 2, 4')
        self.assertEqual(obj.under_ca_cb, 'under_ca_cb: 2, 4')
        self.assertEqual(obj.calls, [('under_ca_cb', 2, 4)])
        self.assertEqual(obj._under_ca_cb, 'under_ca_cb: 2, 4')
        self.assertEqual(obj.__cache_control__,
                         {'under_ca_cb': {'a': 2, 'b': 4}})
