# -*- coding: utf-8 -*-
"""
    __init__.py
    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""

from trytond.pool import Pool
from complaint import Type, Complaint, Action, Action_SaleLine, \
     Action_InvoiceLine
from sale import Configuration, Sale
from model import ModelAccess, ReferenceField  # noqa


def register():
    Pool.register(
        ModelAccess,
        Type,
        Complaint,
        Action,
        Action_SaleLine,
        Action_InvoiceLine,
        Configuration,
        Sale,
        module='sale_complaint', type_='model')
