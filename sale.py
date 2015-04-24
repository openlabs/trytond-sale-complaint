# -*- coding: utf-8 -*-
"""
    sale.py
    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Configuration', 'Sale']
__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'sale.configuration'

    complaint_sequence = fields.Property(
        fields.Many2One(
            'ir.sequence',
            'Complaint Sequence', domain=[
                ('code', '=', 'sale.complaint'),
                ['OR',
                    ('company', '=', Eval('context', {}).get('company', -1)),
                    ('company', '=', None),
                    ],
            ]
        )
    )


class Sale:
    __name__ = 'sale.sale'

    # XXX: Remove this field defination from here when moving to tryton
    # 3.6 as 3.6 already has origin field on sale
    origin = fields.Reference(
        'Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('state') != 'draft',
        },
        depends=['state']
    )

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['sale.sale', 'sale.complaint']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
            ('model', 'in', models),
        ])
        return [(None, '')] + [(m.model, m.name) for m in models]
