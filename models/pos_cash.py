# -*- coding: utf-8 -*-

from odoo import models, fields, api
import pdb


class PosSession(models.Model):
    _inherit = 'pos.session'

    bank_amount = fields.Monetary("Transacciones Bancarias", help="Pedidos y facturas cobrados por bancos")

    daily_invoices_amount = fields.Monetary("Efectivo facturas", compute="_compute_daily_invoices",
                                            help="Total cobrado en efectivo de facturas en el día")
    daily_invoices = fields.Many2many("account.payment", compute="_compute_daily_invoices",
                                      string="Facturas del Día", help="Facturas cobradas en el día")

    external_transactions_amount = fields.Monetary("Salidas de Efectivo", compute="_compute_external_transactions",
                                                   help="Total de salidas de efectivos a bancos")
    external_transactions = fields.One2many("account.payment", "pos_transactions",
                                            string="Resumen salidas a bancos",
                                            help="Crear para generar salida a bancos")

    daily_billing = fields.Monetary("TOTAL")

    @api.onchange('external_transactions')
    def _compute_daily_invoices(self):
        for session in self:
            session.daily_invoices_amount = 0
            session.daily_invoices = False
            possible_invoices = self.env['account.payment'].search([
                ('payment_date', '=', session.start_at),
                ('company_id', '=', session.config_id.company_id.id),
                ('payment_type', '=', 'inbound'),
                ('journal_id.type', '=', 'cash')])
            last_invoices = []
            for possible in possible_invoices:
                if possible.has_invoices:
                    last_invoices.append(possible.id)
            session.daily_invoices = self.env['account.payment'].browse(last_invoices)
            total_daily = 0.0
            for payment_reg in session.daily_invoices:
                total_daily += payment_reg.amount
            session.daily_invoices_amount = total_daily
            session.cash_register_balance_end += total_daily
            session.cash_register_difference -= total_daily

    @api.onchange('external_transactions')
    def _compute_external_transactions(self):
        for session in self:
            session.external_transactions_amount = 0.0
            total_transactions = 0.0
            for transaction in session.external_transactions:
                total_transactions += transaction.amount
            session.external_transactions_amount = total_transactions
            session.cash_register_balance_end -= total_transactions
            session.cash_register_difference += total_transactions





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