# -*- coding: utf-8 -*-

from odoo import models, fields, api
import pdb


class PosSession(models.Model):
    _inherit = 'pos.session'

    bank_amount = fields.Monetary("Transacciones Bancarias", help="Pedidos y facturas cobrados por bancos")

    daily_invoices_amount = fields.Monetary("Efectivo facturas", compute="_compute_daily_invoices",
                                            help="Total cobrado en efectivo de facturas en el día")
    daily_invoices = fields.Many2many("account.payment", compute="_compute_daily_invoices",
                                      string="Facturas del Día", help="Facturas cobradas en el día",
                                      store=True)

    external_transactions_amount = fields.Monetary("Salidas de Efectivo", compute="_compute_daily_invoices",
                                                   help="Total de salidas de efectivos a bancos")
    external_transactions = fields.One2many("account.payment", "pos_transactions",
                                            string="Resumen salidas a bancos",
                                            help="Crear para generar salida a bancos", store=True)

    daily_billing = fields.Monetary("TOTAL", compute="_compute_daily_invoices")

    @api.onchange('external_transactions')
    def _compute_daily_invoices(self):
        for session in self:
            session.daily_invoices_amount = 0
            session.daily_invoices = False
            possible_invoices = self.env['account.payment'].search([
                ('payment_date', '=', session.start_at),
                ('company_id', '=', session.config_id.company_id.id),
                # ('payment_type', '=', 'inbound'),
                ('journal_id.type', '=', 'cash')])
            last_invoices = []
            for possible in possible_invoices:
                if possible.has_invoices:
                    # pdb.set_trace()
                    for finished_sessions in self.env['pos.session'].search([('id', '!=', session.id)]):
                        if not possible in finished_sessions.daily_invoices:
                            last_invoices.append(possible.id)
                            break
            session.daily_invoices = self.env['account.payment'].browse(last_invoices)

            # Invoice payment transactions
            total_daily = 0.0
            for payment_reg in session.daily_invoices:
                if payment_reg.payment_type == "inbound":
                    total_daily += payment_reg.amount
                else:
                    total_daily -= payment_reg.amount
            session.daily_invoices_amount = total_daily

            # Bank transactions
            session.external_transactions_amount = 0.0
            total_transactions = 0.0
            for transaction in session.external_transactions:
                total_transactions += transaction.amount
            session.external_transactions_amount = total_transactions

            # Update cash journal
            session.cash_register_id.balance_external_transaction = total_transactions - total_daily
            session.cash_register_id.total_entry_encoding = sum(
                [line.amount for line in session.cash_register_id.line_ids])
            session.cash_register_id.balance_end = session.cash_register_id.balance_start + session.cash_register_id.total_entry_encoding - session.cash_register_id.balance_external_transaction
            session.cash_register_id.difference = session.cash_register_id.balance_end_real - session.cash_register_id.balance_end

            # Update daily billing
            session.daily_billing = session.cash_register_total_entry_encoding + total_daily
            session.daily_billing += sum([line.balance_end for line in session.statement_ids if line.journal_id.type != 'cash'])

class AccountBankStatement(models.Model):

    @api.one
    @api.depends('line_ids', 'balance_start', 'line_ids.amount', 'balance_end_real', 'balance_external_transaction')
    def _end_balance(self):
        self.total_entry_encoding = sum([line.amount for line in self.line_ids])
        self.balance_end = self.balance_start + self.total_entry_encoding - self.balance_external_transaction
        self.difference = self.balance_end_real - self.balance_end

    _inherit = "account.bank.statement"

    balance_external_transaction = fields.Monetary('External Transactions')

class AccountBankStmtCashWizard(models.Model):
    """
    Account Bank Statement popup that allows entering cash details.
    """
    _inherit = 'account.bank.statement.cashbox'
    _description = 'Account Bank Statement Cashbox Details'

    # cashbox_lines_ids = fields.One2many('account.cashbox.line', 'cashbox_id', string='Cashbox Lines')

    @api.multi
    def validate(self):
        bnk_stmt_id = self.env.context.get('bank_statement_id', False) or self.env.context.get('active_id', False)
        bnk_stmt = self.env['account.bank.statement'].browse(bnk_stmt_id)
        total = 0.0
        for lines in self.cashbox_lines_ids:
            total += lines.subtotal

        pos_session = self.env['pos.session'].browse(self._context.get('active_id'))

        external_trans = pos_session.external_transactions_amount - pos_session.daily_invoices_amount
        if self.env.context.get('balance', False) == 'start':
            # starting balance
            bnk_stmt.write({'balance_start': total, 'balance_external_transaction': external_trans, 'cashbox_start_id': self.id})
        else:
            # closing balance
            bnk_stmt.write({'balance_end_real': total, 'balance_external_transaction': external_trans, 'cashbox_end_id': self.id})
        return {'type': 'ir.actions.act_window_close'}


class AccountPaymentPos(models.Model):
    _inherit = "account.payment"

    pos_transactions = fields.Many2one("pos.session")

    @api.onchange('payment_type')
    def onch_set_journal(self):
        for payment in self:
            if payment.payment_type == "transfer":
                origin_id = self.env['account.journal'].search(
                    ['&', ('journal_user', '=', True), ('type', '=', 'cash'),
                     ('company_id', '=', self.env.user.company_id.id)])[0]
                destination_id = self.env['account.journal'].search(
                    ['&', ('journal_user', '=', True), ('type', '=', 'bank'),
                     ('company_id', '=', self.env.user.company_id.id)])[0]
                # pdb.set_trace()
                payment_method = self.env['account.payment.method'].search([('code', '=', 'manual'), ('payment_type', '=', 'outbound')])[0]
                payment.journal_id = origin_id.id
                payment.destination_journal_id = destination_id.id
                payment.payment_method_id = payment_method.id

    @api.onchange('amount')
    def check_positive_value(self):
        for payment in self:
            if payment.amount < 0:
                payment.amount = 0
                return {'warning': {
                                    'title': 'Advertencia!!',
                                    'message': 'No se pueden incluir cantidades negativas.',
                                    }
                            }