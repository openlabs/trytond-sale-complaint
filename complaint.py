# -*- coding: utf-8 -*-
"""
    complaint.py
    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import warnings
import datetime
import time
from decimal import Decimal
from collections import defaultdict

from trytond.model import ModelSQL, ModelView, Workflow, fields, ModelStorage
from trytond.model.modelstorage import EvalEnvironment
from trytond.pyson import Eval, If, Bool, Id
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder, PYSONDecoder, PYSON
from trytond import backend
from trytond.cache import freeze

from model import ReferenceField


__all__ = ['Type', 'Complaint', 'Action',
    'Action_SaleLine', 'Action_InvoiceLine']


class Type(ModelSQL, ModelView):
    'Customer Complaint Type'
    __name__ = 'sale.complaint.type'

    name = fields.Char('Name', required=True)
    origin = fields.Many2One('ir.model', 'Origin', required=True,
        domain=[('model', 'in', ['sale.sale', 'sale.line',
                    'account.invoice', 'account.invoice.line'])])


class Complaint(Workflow, ModelSQL, ModelView):
    'Customer Complaint'
    __name__ = 'sale.complaint'
    _rec_name = 'reference'

    _states = {
        'readonly': Eval('state') != 'draft',
    }
    _depends = ['state']

    reference = fields.Char('Reference', readonly=True, select=True)
    date = fields.Date('Date', states=_states, depends=_depends)
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states=_states, depends=_depends)
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('customer'))],
        states=_states, depends=_depends + ['customer'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_states, depends=_depends)
    employee = fields.Many2One('company.employee', 'Employee',
        states=_states, depends=_depends)
    type = fields.Many2One('sale.complaint.type', 'Type', required=True,
        states=_states, depends=_depends)
    origin = ReferenceField('Origin', selection='get_origin',
        states={
            'readonly': ((Eval('state') != 'draft')
                | Bool(Eval('actions', [0]))),
            'required': Bool(Eval('origin_model')),
        },
        depends=['state', 'customer', 'origin_model', 'company'])
    origin_id = fields.Function(fields.Integer('Origin ID'),
        'on_change_with_origin_id')
    origin_model = fields.Function(fields.Char('Origin Model'),
        'on_change_with_origin_model')
    description = fields.Text('Description', states=_states, depends=_depends)
    actions = fields.One2Many('sale.complaint.action', 'complaint', 'Actions',
        states=_states, depends=_depends + ['origin_model', 'origin_id'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ], 'State', readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super(Complaint, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._error_messages.update({
            'delete_draft': ('Complaint "%s" must be in draft '
                'to be deleted.'),
            'invalid_origin': "The Origin on record %s is not valid "
                "according to its domain.",
        })
        cls._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'draft'),
                ('waiting', 'approved'),
                ('waiting', 'rejected'),
                ('approved', 'done'),
                ('draft', 'cancelled'),
                ('waiting', 'cancelled'),
                ('done', 'draft'),
                ('cancelled', 'draft'),
            )
        )
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'waiting']),
                },
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['waiting', 'done', 'cancelled']),
                    'icon': If(Eval('state').in_(['done', 'cancelled']),
                        'tryton-clear', 'tryton-go-previous'),
                },
                'wait': {
                    'invisible': ~Eval('state').in_(['draft']),
                },
                'approve': {
                    'invisible': (~Eval('state').in_(['waiting'])
                        & Eval('context', {}).get('groups', []).contains(
                            Id('sale', 'group_sale_admin'))),
                },
                'reject': {
                    'invisible': (~Eval('state').in_(['waiting'])
                        & Eval('context', {}).get('groups', []).contains(
                            Id('sale', 'group_sale_admin'))),
                },
                'process': {
                    'invisible': ~Eval('state').in_(['approved']),
                },
            }
        )

        actions_domains = cls._actions_domains()
        actions_domain = [('action', 'in', actions_domains.pop(None))]
        for model, actions in actions_domains.iteritems():
            actions_domain = If(Eval('origin_model') == model,
                [('action', 'in', actions)], actions_domain)
        cls.actions.domain = [actions_domain]

    @classmethod
    def _origin_domains(cls, party_id, company_id):
        return {
            'sale.sale': [
                ('party', '=', party_id),
                ('company', '=', company_id),
                ('state', 'in', ['confirmed', 'processing', 'done']),
            ],
            'sale.line': [
                ('sale.party', '=', party_id),
                ('sale.company', '=', company_id),
                ('sale.state', 'in', ['confirmed', 'processing', 'done']),
            ],
            'account.invoice': [
                ('party', '=', party_id),
                ('company', '=', company_id),
                ('type', '=', 'out_invoice'),
                ('state', 'in', ['posted', 'paid']),
            ],
            'account.invoice.line': [
                ('invoice.party', '=', party_id),
                ('invoice.company', '=', company_id),
                ('invoice.type', '=', 'out_invoice'),
                ('invoice.state', 'in', ['posted', 'paid']),
            ],
        }

    @classmethod
    def _actions_domains(cls):
        return {
            None: [],
            'sale.sale': ['sale_return'],
            'sale.line': ['sale_return'],
            'account.invoice': ['credit_note'],
            'account.invoice.line': ['credit_note'],
        }

    @staticmethod
    def default_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('type')
    def get_origin(self):
        if self.type:
            origin = self.type.origin
            return [('', ''), (origin.model, origin.name)]
        else:
            return []

    @fields.depends('origin')
    def on_change_with_origin_id(self, name=None):
        if self.origin:
            return self.origin.id

    @fields.depends('origin')
    def on_change_with_origin_model(self, name=None):
        if self.origin:
            return self.origin.__class__.__name__

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('sale.configuration')

        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('reference'):
                config = Configuration(1)
                values['reference'] = Sequence.get_id(
                    config.complaint_sequence.id)
        return super(Complaint, cls).create(vlist)

    @classmethod
    def copy(cls, complaints, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['reference'] = None
        return super(Complaint, cls).copy(complaints, default=default)

    @classmethod
    def delete(cls, complaints):
        for complaint in complaints:
            if complaint.state != 'draft':
                cls.raise_user_error('delete_draft', complaint.rec_name)
        super(Complaint, cls).delete(complaints)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    def reject(cls, complaints):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, complaints):
        results = defaultdict(list)
        actions = defaultdict(list)
        for complaint in complaints:
            for action in complaint.actions:
                if action.result:
                    continue
                result = action.do()
                results[result.__class__].append(result)
                actions[result.__class__].append(action)
        for kls, records in results.iteritems():
            for record in records:
                record.save()
            for action, record in zip(actions[kls], records):
                action.result = record
                action.save()

    @classmethod
    def validate(cls, records):
        """
        Validate records
        """
        super(Complaint, cls).validate(records)

        cls.validate_origin_with_domain(records)

    @classmethod
    def validate_origin_with_domain(cls, records):
        """
        Validate for correct domain on origin
        """
        for record in records:
            if not record.origin_model:
                continue

            domain = cls._origin_domains(
                record.customer.id, record.company.id)[record.origin_model]
            domain += [('id', '=', record.origin_id)]

            Model = Pool().get(record.origin_model)

            if Model.search(domain, count=True) != 1:
                cls.raise_user_error('invalid_origin', (record.id,))

    @classmethod
    def _validate(cls, records, field_names=None):  # pragma: no cover
        """
        Rewriting this method from ModelStorage temporarily until the fix
        for Reference field is pushed to 3.4
        """
        pool = Pool()
        # Ensure that records are readable
        with Transaction().set_context(_check_access=False):
            records = cls.browse(records)

        def call(name):
            method = getattr(cls, name)
            if not hasattr(method, 'im_self') or method.im_self:
                return method(records)
            else:
                return all(method(r) for r in records)
        for field in cls._constraints:
            warnings.warn(
                '_constraints is deprecated, override validate instead',
                DeprecationWarning, stacklevel=2)
            if not call(field[0]):
                cls.raise_user_error(field[1])

        ctx_pref = {}
        if Transaction().user:
            try:
                User = pool.get('res.user')
            except KeyError:
                pass
            else:
                ctx_pref = User.get_preferences(context_only=True)

        def is_pyson(test):
            if isinstance(test, PYSON):
                return True
            if isinstance(test, (list, tuple)):
                for i in test:
                    if isinstance(i, PYSON):
                        return True
                    if isinstance(i, (list, tuple)):
                        if is_pyson(i):
                            return True
            if isinstance(test, dict):
                for key, value in test.items():
                    if isinstance(value, PYSON):
                        return True
                    if isinstance(value, (list, tuple, dict)):
                        if is_pyson(value):
                            return True
            return False

        def validate_domain(field):
            if not field.domain:
                return
            if field._type in ['dict', 'reference']:
                return
            if field._type in ('many2one', 'one2many'):
                Relation = pool.get(field.model_name)
            elif field._type in ('many2many', 'one2one'):
                Relation = field.get_target()
            else:
                Relation = cls
            domains = defaultdict(list)
            if is_pyson(field.domain):
                pyson_domain = PYSONEncoder().encode(field.domain)
                for record in records:
                    env = EvalEnvironment(record, cls)
                    env.update(Transaction().context)
                    env['current_date'] = datetime.datetime.today()
                    env['time'] = time
                    env['context'] = Transaction().context
                    env['active_id'] = record.id
                    domain = freeze(PYSONDecoder(env).decode(pyson_domain))
                    domains[domain].append(record)
            else:
                domains[freeze(field.domain)].extend(records)

            for domain, sub_records in domains.iteritems():
                validate_relation_domain(field, sub_records, Relation, domain)

        def validate_relation_domain(field, records, Relation, domain):
            if field._type in ('many2one', 'one2many', 'many2many', 'one2one'):
                relations = []
                for record in records:
                    if getattr(record, field.name):
                        if field._type in ('many2one', 'one2one'):
                            relations.append(getattr(record, field.name))
                        else:
                            relations.extend(getattr(record, field.name))
            else:
                relations = records
            if relations:
                finds = Relation.search(['AND',
                    [('id', 'in', [r.id for r in relations])],
                    domain,
                ])
                if set(relations) != set(finds):
                    cls.raise_user_error('domain_validation_record',
                        error_args=cls._get_error_args(field.name))

        field_names = set(field_names or [])
        function_fields = {name for name, field in cls._fields.iteritems()
            if isinstance(field, fields.Function)}
        ctx_pref['active_test'] = False
        with Transaction().set_context(ctx_pref):
            for field_name, field in cls._fields.iteritems():
                depends = set(field.depends)
                if (field_names
                        and field_name not in field_names
                        and not (depends & field_names)
                        and not (depends & function_fields)):
                    continue
                if isinstance(field, fields.Function) and \
                        not field.setter:
                    continue

                validate_domain(field)

                def required_test(value, field_name):
                    if (isinstance(value, (type(None), type(False), list,
                                    tuple, basestring, dict))
                            and not value):
                        cls.raise_user_error('required_validation_record',
                            error_args=cls._get_error_args(field_name))
                # validate states required
                if field.states and 'required' in field.states:
                    if is_pyson(field.states['required']):
                        pyson_required = PYSONEncoder().encode(
                                field.states['required'])
                        for record in records:
                            env = EvalEnvironment(record, cls)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            required = PYSONDecoder(env).decode(pyson_required)
                            if required:
                                required_test(getattr(record, field_name),
                                    field_name)
                    else:
                        if field.states['required']:
                            for record in records:
                                required_test(getattr(record, field_name),
                                    field_name)
                # validate required
                if field.required:
                    for record in records:
                        required_test(getattr(record, field_name), field_name)
                # validate size
                if hasattr(field, 'size') and field.size is not None:
                    for record in records:
                        if isinstance(field.size, PYSON):
                            pyson_size = PYSONEncoder().encode(field.size)
                            env = EvalEnvironment(record, cls)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            field_size = PYSONDecoder(env).decode(pyson_size)
                        else:
                            field_size = field.size
                        size = len(getattr(record, field_name) or '')
                        if (size > field_size >= 0):
                            error_args = cls._get_error_args(field_name)
                            error_args['size'] = size
                            cls.raise_user_error('size_validation_record',
                                error_args=error_args)

                def digits_test(value, digits, field_name):
                    def raise_user_error(value):
                        error_args = cls._get_error_args(field_name)
                        error_args['digits'] = digits[1]
                        error_args['value'] = repr(value)
                        cls.raise_user_error('digits_validation_record',
                            error_args=error_args)
                    if value is None:
                        return
                    if isinstance(value, Decimal):
                        if (value.quantize(Decimal(str(10.0 ** -digits[1])))
                                != value):
                            raise_user_error(value)
                    elif backend.name() != 'mysql':
                        if not (round(value, digits[1]) == float(value)):
                            raise_user_error(value)
                # validate digits
                if hasattr(field, 'digits') and field.digits:
                    if is_pyson(field.digits):
                        pyson_digits = PYSONEncoder().encode(field.digits)
                        for record in records:
                            env = EvalEnvironment(record, cls)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            digits = PYSONDecoder(env).decode(pyson_digits)
                            digits_test(getattr(record, field_name), digits,
                                field_name)
                    else:
                        for record in records:
                            digits_test(getattr(record, field_name),
                                field.digits, field_name)

                # validate selection
                if hasattr(field, 'selection') and field.selection:
                    if isinstance(field.selection, (tuple, list)):
                        test = set(dict(field.selection).keys())
                    for record in records:
                        value = getattr(record, field_name)
                        if field._type == 'reference':
                            if isinstance(value, ModelStorage):
                                value = value.__class__.__name__
                            elif value:
                                value, _ = value.split(',')
                        if not isinstance(field.selection, (tuple, list)):
                            sel_func = getattr(cls, field.selection)
                            if (not hasattr(sel_func, 'im_self')
                                    or sel_func.im_self):
                                test = sel_func()
                            else:
                                test = sel_func(record)
                            test = set(dict(test))
                        # None and '' are equivalent
                        if '' in test or None in test:
                            test.add('')
                            test.add(None)
                        if value not in test:
                            error_args = cls._get_error_args(field_name)
                            error_args['value'] = value
                            cls.raise_user_error('selection_validation_record',
                                error_args=error_args)

                def format_test(value, format, field_name):
                    if not value:
                        return
                    if not isinstance(value, datetime.time):
                        value = value.time()
                    if value != datetime.datetime.strptime(
                            value.strftime(format), format).time():
                        error_args = cls._get_error_args(field_name)
                        error_args['value'] = value
                        cls.raise_user_error('time_format_validation_record',
                            error_args=error_args)

                # validate time format
                if (field._type in ('datetime', 'time')
                        and field_name not in ('create_date', 'write_date')):
                    if is_pyson(field.format):
                        pyson_format = PYSONDecoder().encode(field.format)
                        for record in records:
                            env = EvalEnvironment(record, cls)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            format = PYSONDecoder(env).decode(pyson_format)
                            format_test(getattr(record, field_name), format,
                                field_name)
                    else:
                        for record in records:
                            format_test(getattr(record, field_name),
                                field.format, field_name)

        for record in records:
            record.pre_validate()

        cls.validate(records)


class Action(ModelSQL, ModelView):
    'Customer Complaint Action'
    __name__ = 'sale.complaint.action'

    _states = {
        'readonly': Bool(Eval('result')),
    }
    _depends = ['result']
    _line_states = {
        'invisible': Eval('_parent_complaint', {}
            ).get('origin_model', 'sale.line') != 'sale.line',
        'readonly': _states['readonly'],
    }
    _line_depends = _depends

    complaint = fields.Many2One('sale.complaint', 'Complaint', required=True,
        states=_states, depends=_depends)
    action = fields.Selection([
        ('sale_return', 'Create Sale Return'),
        ('credit_note', 'Create Credit Note'),
    ], 'Action')

    sale_lines = fields.Many2Many('sale.complaint.action-sale.line',
        'action', 'line', 'Sale Lines',
        domain=[('sale', '=', Eval('_parent_complaint', {}).get('origin_id'))],
        states={
            'invisible': Eval('_parent_complaint', {}
                ).get('origin_model', 'sale.sale') != 'sale.sale',
            'readonly': _states['readonly'],
        },
        depends=_depends,
        help='Leave empty for all lines')

    invoice_lines = fields.Many2Many(
        'sale.complaint.action-account.invoice.line', 'action', 'line',
        'Invoice Lines',
        domain=[('invoice', '=', Eval('_parent_complaint', {}
                    ).get('origin_id'))],
        states={
            'invisible': Eval('_parent_complaint', {}
                ).get('origin_model', 'account.invoice.line'
                ) != 'account.invoice',
            'readonly': _states['readonly'],
        },
        depends=_depends,
        help='Leave empty for all lines')

    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states=_line_states, depends=_line_depends + ['unit_digits'],
        help='Leave empty for the same quantity')
    unit = fields.Function(fields.Many2One('product.uom', 'Unit',
            states=_line_states, depends=_line_depends),
        'on_change_with_unit')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'get_unit_digits')
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
        states=_line_states, depends=_line_depends,
        help='Leave empty for the same price')

    result = fields.Reference('Result', selection='get_result', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Action, cls).__setup__()
        cls._error_messages.update({
            'delete_result': ('Action "%s" must not have result '
                'to be deleted.'),
        })

    @fields.depends('complaint')
    def on_change_with_unit(self, name=None):
        if self.complaint.origin_model == 'sale.line':
            return self.complaint.origin.unit.id

    @fields.depends('complaint')
    def get_unit_digits(self, name=None):
        if self.complaint.origin_model == 'sale.line':
            return self.complaint.origin.unit.digits
        return 2

    @classmethod
    def _get_result(cls):
        'Return list of Model names for result Reference'
        return ['sale.sale', 'account.invoice']

    @classmethod
    def get_result(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_result()
        models = Model.search([
            ('model', 'in', models),
        ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    def do(self):
        return getattr(self, 'do_%s' % self.action)()

    def do_sale_return(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')

        if isinstance(self.complaint.origin, (Sale, Line)):
            default = {}
            if isinstance(self.complaint.origin, Sale):
                sale = self.complaint.origin
                sale_lines = self.sale_lines or sale.lines
            elif isinstance(self.complaint.origin, Line):
                sale_line = self.complaint.origin
                sale = sale_line.sale
                sale_lines = [sale_line]
                if self.quantity is not None:
                    default['quantity'] = self.quantity
                if self.unit_price is not None:
                    default['unit_price'] = self.unit_price
            return_sale, = Sale.copy([sale], default={'lines': None})
            default['sale'] = return_sale.id
            Line.copy(sale_lines, default=default)
        else:
            return
        return_sale.origin = self.complaint
        for line in return_sale.lines:
            if line.type == 'line':
                line.quantity *= -1
        return_sale.lines = return_sale.lines  # Force saving
        return return_sale

    def do_credit_note(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.invoice.line')

        if isinstance(self.complaint.origin, (Invoice, Line)):
            if isinstance(self.complaint.origin, Invoice):
                invoice = self.complaint.origin
                invoice_lines = self.invoice_lines or invoice.lines
            elif isinstance(self.complaint.origin, Line):
                invoice_line = self.complaint.origin
                invoice = invoice_line.invoice
                invoice_lines = [invoice_line]
            values = invoice._credit()
            lines_values = []
            for invoice_line in invoice_lines:
                lines_values.append(invoice_line._credit())
            if isinstance(self.complaint.origin, Line):
                if self.quantity is not None:
                    lines_values[0]['quantity'] = self.quantity
                if self.unit_price is not None:
                    lines_values[0]['unit_price'] = self.unit_price
            values['lines'] = [('create', lines_values)]
            del values['taxes']
            credit_note, = Invoice.create([values])
            Invoice.update_taxes([credit_note])
        else:
            return
        return credit_note

    @classmethod
    def delete(cls, actions):
        for action in actions:
            if action.result:
                cls.raise_user_error('delete_result', action.rec_name)
        super(Action, cls).delete(actions)


class Action_SaleLine(ModelSQL):
    'Customer Complaint Action - Sale Line'
    __name__ = 'sale.complaint.action-sale.line'

    action = fields.Many2One('sale.complaint.action', 'Action',
        ondelete='CASCADE', select=True, required=True)
    line = fields.Many2One('sale.line', 'Sale Line', ondelete='RESTRICT',
        required=True)


class Action_InvoiceLine(ModelSQL):
    'Customer Complaint Action - Invoice Line'
    __name__ = 'sale.complaint.action-account.invoice.line'

    action = fields.Many2One('sale.complaint.action', 'Action',
        ondelete='CASCADE', select=True, required=True)
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='RESTRICT', required=True)
