# -*- coding: utf-8 -*-
"""
    sale.py
    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import PoolMeta
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

    @classmethod
    def _get_origin(cls):
        return super(Sale, cls)._get_origin() + ['sale.complaint']
