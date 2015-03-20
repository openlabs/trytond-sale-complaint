# -*- coding: utf-8 -*-
"""
    model.py
    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import warnings

from trytond.pool import Pool, PoolMeta
from trytond.model.fields import Reference

__all__ = ['ModelAccess', 'ReferenceField']
__metaclass__ = PoolMeta


class ModelAccess:
    __name__ = 'ir.model.access'

    @classmethod
    def check_relation(cls, model_name, field_name, mode='read'):  # pragma: no cover  # noqa
        """
        Rewriting this method from ModelStorage temporarily until the fix
        for Reference field is pushed to 3.4
        """
        pool = Pool()
        Model = pool.get(model_name)
        field = getattr(Model, field_name)
        if field._type in ('one2many', 'many2one'):
            return cls.check(field.model_name, mode=mode,
                raise_exception=False)
        elif field._type in ('many2many', 'one2one'):
            if (field.target
                    and not cls.check(field.target, mode=mode,
                        raise_exception=False)):
                return False
            elif (field.relation_name
                    and not cls.check(field.relation_name, mode=mode,
                        raise_exception=False)):
                return False
            else:
                return True
        elif field._type == 'reference':
            selection = field.selection
            if isinstance(selection, basestring):
                sel_func = getattr(Model, field.selection)
                if (not hasattr(sel_func, 'im_self')
                        or sel_func.im_self):
                    selection = sel_func()
                else:
                    # XXX Can not check access right on instance method
                    selection = []
            for model_name, _ in selection:
                if not cls.check(model_name, mode=mode,
                        raise_exception=False):
                    return False
            return True
        else:
            return True


class ReferenceField(Reference):

    def __init__(self, string='', selection=None, selection_change_with=None,
            help='', required=False, readonly=False, domain=None, states=None,
            select=False, on_change=None, on_change_with=None, depends=None,
            context=None, loading='lazy'):
        """
        Rewriting this method from ModelStorage temporarily until the fix
        for Reference field is pushed to 3.4
        """
        super(ReferenceField, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.selection = selection or None
        self.selection_change_with = set()
        if selection_change_with:  # pragma: no cover
            warnings.warn('selection_change_with argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=2)
            self.selection_change_with |= set(selection_change_with)
