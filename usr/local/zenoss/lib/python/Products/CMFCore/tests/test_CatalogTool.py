##############################################################################
#
# Copyright (c) 2001 Zope Foundation and Contributors.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
""" Unit tests for CatalogTool module.
"""

import unittest

from Acquisition import Implicit
from zope.interface import implements
from Products.CMFCore.interfaces import ICatalogTool
from Products.CMFCore.tests.base.dummy import DummyContent
from Products.CMFCore.interfaces import IIndexableObject
from Products.CMFCore.interfaces import IContentish
from Products.CMFCore.tests.base.testcase import SecurityTest


class FakeFolder(Implicit):
    id = 'portal'


class FakeCatalog(Implicit):
    implements(ICatalogTool)
    id = 'portal_catalog'


class FakeWorkflowTool(Implicit):
    id = 'portal_workflow'

    def __init__(self, vars):
        self._vars = vars

    def getCatalogVariablesFor(self, ob):
        return self._vars


class CatalogDummyContent(DummyContent):

    """ Dummy content that already provides IIndexableObject
        and therefore does not need a wrapper to be registered
    """

    implements(IIndexableObject)
    allowedRolesAndUsers = ['Manager'] # default value


class IndexableObjectWrapperTests(unittest.TestCase):

    def _getTargetClass(self):
        from Products.CMFCore.CatalogTool import IndexableObjectWrapper

        return IndexableObjectWrapper

    def _makeOne(self, vars, obj):
        self.root = FakeFolder()
        self.root.portal_catalog = FakeCatalog()
        self.root.portal_workflow = FakeWorkflowTool(vars)
        catalog = self.root.portal_catalog
        return self._getTargetClass()(obj, catalog)

    def _makeContent(self, *args, **kw):
        from Products.CMFCore.tests.base.dummy import DummyContent

        return DummyContent(*args, **kw)

    def test_interfaces(self):
        from zope.interface.verify import verifyClass
        from Products.CMFCore.interfaces import IIndexableObjectWrapper

        verifyClass(IIndexableObjectWrapper, self._getTargetClass())

    def test_allowedRolesAndUsers(self):
        # XXX This test fails when verbose security is enabled in zope.conf,
        # because the roles will then contain '_View_Permission' as well as
        # 'Manager'.
        obj = self._makeContent()
        w = self._makeOne({}, obj)
        self.assertEqual(w.allowedRolesAndUsers(), ['Manager'])

    def test___str__(self):
        obj = self._makeContent('foo')
        w = self._makeOne({}, obj)
        self.assertEqual(str(w), str(obj))

    def test_proxied_attributes(self):
        obj = self._makeContent('foo')
        obj.title = 'Foo'
        w = self._makeOne({}, obj)
        self.assertEqual(w.getId(), 'foo')
        self.assertEqual(w.Title(), 'Foo')

    def test_vars(self):
        obj = self._makeContent()
        w = self._makeOne({'bar': 1, 'baz': 2}, obj)
        self.assertEqual(w.bar, 1)
        self.assertEqual(w.baz, 2)

    def test_provided(self):
        from Products.CMFCore.interfaces import IIndexableObjectWrapper
        from Products.CMFCore.interfaces import IIndexableObject

        obj = self._makeContent()
        w = self._makeOne({}, obj)
        self.failUnless(IContentish.providedBy(w))
        self.failUnless(IIndexableObjectWrapper.providedBy(w))
        self.failUnless(IIndexableObject.providedBy(w))

    def test_adapts(self):
        from zope.component import adaptedBy
        from Products.CMFCore.interfaces import ICatalogTool

        w = self._getTargetClass()
        adapts = adaptedBy(w)
        self.assertEqual(adapts, (IContentish, ICatalogTool))


class CatalogToolTests(SecurityTest):

    def _getTargetClass(self):
        from Products.CMFCore.CatalogTool import CatalogTool

        return CatalogTool

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def _makeContent(self, *args, **kw):
        return CatalogDummyContent(*args, **kw)

    def test_interfaces(self):
        from zope.interface.verify import verifyClass
        from Products.CMFCore.interfaces import IActionProvider
        from Products.CMFCore.interfaces import ICatalogTool
        from Products.ZCatalog.interfaces import IZCatalog

        verifyClass(IActionProvider, self._getTargetClass())
        verifyClass(ICatalogTool, self._getTargetClass())
        verifyClass(IZCatalog, self._getTargetClass())

    def loginWithRoles(self, *roles):
        from AccessControl.SecurityManagement import newSecurityManager
        from Products.CMFCore.tests.base.security import UserWithRoles
        user = UserWithRoles(*roles).__of__(self.root)
        newSecurityManager(None, user)

    def loginManager(self):
        from AccessControl.SecurityManagement import newSecurityManager
        from Products.CMFCore.tests.base.security import OmnipotentUser
        user = OmnipotentUser().__of__(self.root)
        newSecurityManager(None, user)

    def setupProxyRoles(self, *proxy_roles):
        from AccessControl import getSecurityManager
        class FauxExecutable:
            _proxy_roles = proxy_roles
        sm = getSecurityManager()
        sm.addContext(FauxExecutable())

    def test_processActions(self):
        """
            Tracker #405:  CatalogTool doesn't accept optional third
            argument, 'idxs', to 'catalog_object'.
        """
        tool = self._makeOne()
        tool.addIndex('SearchableText', 'KeywordIndex')
        dummy = self._makeContent(catalog=1)

        tool.catalog_object(dummy, '/dummy')
        tool.catalog_object(dummy, '/dummy', ['SearchableText'])

    def test_search_anonymous(self):
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        dummy = self._makeContent(catalog=1)
        catalog.catalog_object(dummy, '/dummy')

        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(query)))

    def test_search_member_with_valid_roles(self):
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        dummy = self._makeContent(catalog=1)
        dummy.allowedRolesAndUsers = ('Blob', )
        catalog.catalog_object(dummy, '/dummy')

        self.loginWithRoles('Blob')

        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(1, len(catalog.searchResults(query)))

    def test_search_member_with_valid_roles_but_proxy_roles_limit(self):
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        dummy = self._makeContent(catalog=1)
        dummy.allowedRolesAndUsers = ('Blob', )
        catalog.catalog_object(dummy, '/dummy')

        self.loginWithRoles('Blob')
        self.setupProxyRoles('Waggle')

        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(query)))

    def test_search_member_wo_valid_roles(self):
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        dummy = self._makeContent(catalog=1)
        dummy.allowedRoleAndUsers = ('Blob', )
        catalog.catalog_object(dummy, '/dummy')

        self.loginWithRoles('Waggle')

        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(query)))

    def test_search_member_wo_valid_roles_but_proxy_roles_allow(self):
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        dummy = self._makeContent(catalog=1)
        dummy.allowedRolesAndUsers = ('Blob', )
        catalog.catalog_object(dummy, '/dummy')

        self.loginWithRoles('Waggle')
        self.setupProxyRoles('Blob')

        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(1, len(catalog.searchResults(query)))

    def test_search_inactive(self):
        from DateTime.DateTime import DateTime
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('effective', 'DateIndex')
        catalog.addIndex('expires', 'DateIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        now = DateTime()
        dummy = self._makeContent(catalog=1)
        dummy.allowedRolesAndUsers = ('Blob', )

        self.loginWithRoles('Blob')

        # not yet effective
        dummy.effective = now+1
        dummy.expires = now+2
        catalog.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(query)))

        # already expired
        dummy.effective = now-2
        dummy.expires = now-1
        catalog.catalog_object(dummy, '/dummy')
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(query)))

    def test_search_restrict_manager(self):
        from DateTime.DateTime import DateTime
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('effective', 'DateIndex')
        catalog.addIndex('expires', 'DateIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        now = DateTime()
        dummy = self._makeContent(catalog=1)

        self.loginManager()

        # already expired
        dummy.effective = now-4
        dummy.expires = now-2
        catalog.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(1, len(catalog.searchResults(query)))

        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-3, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-1, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-3, 'range': 'max'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-1, 'range': 'max'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': (now-3, now-1), 'range': 'min:max'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': (now-3, now-1), 'range': 'minmax'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-2})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-2, 'range': None})))

    def test_search_restrict_inactive(self):
        from DateTime.DateTime import DateTime
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('effective', 'DateIndex')
        catalog.addIndex('expires', 'DateIndex')
        catalog.addIndex('meta_type', 'FieldIndex')
        now = DateTime()
        dummy = self._makeContent(catalog=1)
        dummy.allowedRolesAndUsers = ('Blob', )

        self.loginWithRoles('Blob')

        # already expired
        dummy.effective = now-4
        dummy.expires = now-2
        catalog.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(query)))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-3, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-3, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now+3, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now+3, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': (now-3, now-1), 'range': 'min:max'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': (now-3, now-1), 'range': 'minmax'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-2, 'range': None})))

    def test_search_restrict_visible(self):
        from DateTime.DateTime import DateTime
        catalog = self._makeOne()
        catalog.addIndex('allowedRolesAndUsers', 'KeywordIndex')
        catalog.addIndex('effective', 'DateIndex')
        catalog.addIndex('expires', 'DateIndex')
        catalog.addIndex('meta_type', 'FieldIndex')

        now = DateTime()
        dummy = self._makeContent(catalog=1)
        dummy.allowedRolesAndUsers = ('Blob', )

        self.loginWithRoles('Blob')

        # visible
        dummy.effective = now-2
        dummy.expires = now+2
        catalog.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(catalog._catalog.searchResults(query)))
        self.assertEqual(1, len(catalog.searchResults(query)))

        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': now-1, 'range': 'min'})))
        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': now-1, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': now+1, 'range': 'min'})))
        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': now+1, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': (now-1, now+1), 'range': 'min:max'})))
        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': (now-1, now+1), 'range': 'minmax'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-2, 'range': None})))

        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': now-3, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': now-3, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': now+3, 'range': 'min'})))
        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': now+3, 'range': 'max'})))
        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': (now-3, now+3), 'range': 'min:max'})))
        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': (now-3, now+3), 'range': 'minmax'})))

        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-1, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-1, 'range': 'max'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now+1, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now+1, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': (now-1, now+1), 'range': 'min:max'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': (now-1, now+1), 'range': 'minmax'})))

        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now-3, 'range': 'min'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now-3, 'range': 'max'})))
        self.assertEqual(0, len(catalog.searchResults(
            expires={'query': now+3, 'range': 'min'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': now+3, 'range': 'max'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': (now-3, now+3), 'range': 'min:max'})))
        self.assertEqual(1, len(catalog.searchResults(
            expires={'query': (now-3, now+3), 'range': 'minmax'})))

        self.assertEqual(1, len(catalog.searchResults(
            effective={'query': now-1, 'range': 'max'},
            expires={'query': now+1, 'range': 'min'})))

        self.assertEqual(0, len(catalog.searchResults(
            effective={'query': now+1, 'range': 'max'},
            expires={'query': now+3, 'range': 'min'})))

    def test_convertQuery(self):
        convert = self._makeOne()._convertQuery

        kw = {}
        convert(kw)
        self.assertEqual(kw, {})

        kw = {'expires': 5, 'expires_usage': 'brrr:min'}
        self.assertRaises(ValueError, convert, kw)

        kw = {'foo': 'bar'}
        convert(kw)
        self.assertEqual(kw, {'foo': 'bar'})

        kw = {'expires': 5, 'expires_usage': 'range:min'}
        convert(kw)
        self.assertEqual(kw, {'expires': {'query': 5, 'range': 'min'}})

        kw = {'expires': 5, 'expires_usage': 'range:max'}
        convert(kw)
        self.assertEqual(kw, {'expires': {'query': 5, 'range': 'max'}})

        kw = {'expires': (5, 7), 'expires_usage': 'range:min:max'}
        convert(kw)
        self.assertEqual(kw, {'expires':
                              {'query': (5, 7), 'range': 'min:max'}})

    def test_refreshCatalog(self):
        from Products.CMFCore.tests.base.dummy import DummySite
        site = DummySite('site').__of__(self.root)
        site._setObject('dummy', self._makeContent(catalog=1))
        site._setObject('portal_catalog', self._makeOne())
        ctool = site.portal_catalog
        ctool.addIndex('meta_type', 'FieldIndex')
        ctool.catalog_object(site.dummy, '/dummy')

        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(ctool._catalog.searchResults(query)))
        ctool.refreshCatalog(clear=1)
        length = len(ctool._catalog.searchResults(query))
        self.assertEqual(1, length,
                         'CMF Collector issue #379 (\'Update Catalog\' '
                         'fails): %s entries after refreshCatalog'
                         % length)

    def test_listAllowedRolesAndUsers_proxyroles(self):
        # https://bugs.launchpad.net/zope-cmf/+bug/161729
        from AccessControl import getSecurityManager
        catalog = self._makeOne()
        self.loginWithRoles('Blob')
        user = getSecurityManager().getUser()

        # First case, no proxy roles set at all
        arus = catalog._listAllowedRolesAndUsers(user)
        self.assertEquals(len(arus), 3)
        self.failUnless('Anonymous' in arus)
        self.failUnless('Blob' in arus)
        self.failUnless('user:%s' % user.getId() in arus)

        # Second case, a proxy role is set
        self.setupProxyRoles('Waggle')
        arus = catalog._listAllowedRolesAndUsers(user)
        self.assertEquals(len(arus), 3)
        self.failUnless('Anonymous' in arus)
        self.failUnless('Waggle' in arus)
        self.failUnless('user:%s' % user.getId() in arus)

        # Third case, proxy roles are an empty tuple. This happens if
        # proxy roles are unset using the ZMI. The behavior should
        # mirror the first case with no proxy role setting at all.
        self.setupProxyRoles()
        arus = catalog._listAllowedRolesAndUsers(user)
        self.assertEquals(len(arus), 3)
        self.failUnless('Anonymous' in arus)
        self.failUnless('Blob' in arus)
        self.failUnless('user:%s' % user.getId() in arus)

    def test_wrapping1(self):
        # DummyContent implements IIndexableObject
        # so should be indexed
        dummy = self._makeContent(catalog=1)
        ctool = self._makeOne()
        ctool.addIndex('meta_type', 'FieldIndex')
        ctool.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(ctool._catalog.searchResults(query)))

    def test_wrapping2(self):
        # DummyContent does not implement IIndexableObject
        # no wrapper registered - should fall back to using
        # wrapper class directly
        dummy = DummyContent(catalog=1)
        ctool = self._makeOne()
        ctool.addIndex('meta_type', 'FieldIndex')
        ctool.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(ctool._catalog.searchResults(query)))

    def test_wrapping3(self):
        # DummyContent does not implement IIndexableObject
        # wrapper registered - should look this up

        def FakeWrapper(object, catalog):
            return object

        from zope.component import getSiteManager
        self.sm = getSiteManager()
        self.sm.registerAdapter(FakeWrapper,
                                (IContentish, ICatalogTool),
                                IIndexableObject)

        dummy = DummyContent(catalog=1)
        ctool = self._makeOne()
        ctool.addIndex('meta_type', 'FieldIndex')
        ctool.catalog_object(dummy, '/dummy')
        query = {'meta_type': 'Dummy'}
        self.assertEqual(1, len(ctool._catalog.searchResults(query)))


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(IndexableObjectWrapperTests),
        unittest.makeSuite(CatalogToolTests),
        ))
