# -*- coding: utf-8 -*-
"""
    tests/__init__.py
    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(
        doctest.DocFileSuite(
            'scenario_sale_complaint.rst',
            setUp=doctest_setup,
            tearDown=doctest_teardown,
            encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE
        )
    )
    return suite
