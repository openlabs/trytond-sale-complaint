=======================
Sale Complaint Scenario
=======================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard, Report
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale_complaint::

    >>> Module = Model.get('ir.module.module')
    >>> sale_module, = Module.find([('name', '=', 'sale_complaint')])
    >>> sale_module.click('install')
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='U.S. Dollar', symbol='$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point='.', mon_thousands_sep=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> Journal = Model.get('account.journal')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')
    >>> cash, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('name', '=', 'Main Cash'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.credit_account = cash
    >>> cash_journal.debit_account = cash
    >>> cash_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create complaint type::

    >>> Type = Model.get('sale.complaint.type')
    >>> IrModel = Model.get('ir.model')
    >>> sale_type = Type(name='Sale')
    >>> sale_type.origin, = IrModel.find([('model', '=', 'sale.sale')])
    >>> sale_type.save()
    >>> sale_line_type = Type(name='Sale Line')
    >>> sale_line_type.origin, = IrModel.find([('model', '=', 'sale.line')])
    >>> sale_line_type.save()
    >>> invoice_type = Type(name='Invoice')
    >>> invoice_type.origin, = IrModel.find(
    ...     [('model', '=', 'account.invoice')])
    >>> invoice_type.save()
    >>> invoice_line_type = Type(name='Invoice Line')
    >>> invoice_line_type.origin, = IrModel.find(
    ...     [('model', '=', 'account.invoice.line')])
    >>> invoice_line_type.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Sale 5 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Post the invoice::

    >>> invoice, = sale.invoices
    >>> invoice.click('post')

Create a complaint to return the sale::

    >>> Complaint = Model.get('sale.complaint')
    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = sale_type
    >>> complaint.origin = sale
    >>> action = complaint.actions.new()
    >>> action.action = 'sale_return'
    >>> complaint.save()
    >>> complaint.state
    u'draft'
    >>> complaint.click('wait')
    >>> complaint.state
    u'waiting'
    >>> complaint.click('approve')
    >>> complaint.state
    u'approved'
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> return_sale = action.result
    >>> len(return_sale.lines)
    2
    >>> sum(l.quantity for l in return_sale.lines)
    -5.0

Create a complaint to return a sale line::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = sale_line_type
    >>> complaint.origin = sale.lines[0]
    >>> action = complaint.actions.new()
    >>> action.action = 'sale_return'
    >>> action.quantity = 1
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> return_sale = action.result
    >>> return_line, = return_sale.lines
    >>> return_line.quantity
    -1.0

Create a complaint to credit the invoice::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = invoice_type
    >>> complaint.origin = invoice
    >>> action = complaint.actions.new()
    >>> action.action = 'credit_note'
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    u'out_credit_note'
    >>> len(credit_note.lines)
    2
    >>> sum(l.quantity for l in credit_note.lines)
    5.0

Create a complaint to credit a invoice line::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = invoice_line_type
    >>> complaint.origin = invoice.lines[0]
    >>> action = complaint.actions.new()
    >>> action.action = 'credit_note'
    >>> action.quantity = 1
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    u'out_credit_note'
    >>> credit_note_line, = credit_note.lines
    >>> credit_note_line.quantity
    1.0
