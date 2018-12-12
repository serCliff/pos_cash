# -*- coding: utf-8 -*-

from odoo import models, fields, api
import pdb


class AccountPaymentPos(models.Model):
    _inherit = "account.payment"

    pos_transactions = fields.Many2one("pos.session")
    pos_invoice_transactions = fields.Many2one("pos.session", string="Pos Session")

    @api.model
    def create(self, vals):
        if vals['payment_type'] == 'inbound' and self.env['account.journal'].browse(vals['journal_id']).type == "cash":
            pos_id = self.env['pos.session'].search(
                ['&', ('config_id.company_id', '=', self.env.user.company_id.id), ('state', '=', 'opened')])
            vals['pos_invoice_transactions'] = pos_id.id

        return super(AccountPaymentPos, self).create(vals)

    @api.onchange('payment_type')
    def onch_set_journal(self):
        """ Metodo para preasignar los diarios cuando se hacen salidas a bancos desde el punto de venta """
        for payment in self:
            if payment.payment_type == "transfer":
                origin_id = self.env['account.journal'].search(
                    ['&', ('journal_user', '=', True), ('type', '=', 'cash'),
                     ('company_id', '=', self.env.user.company_id.id)])[0]
                destination_id = self.env['account.journal'].search(
                    ['&', ('journal_user', '=', True), ('type', '=', 'bank'),
                     ('company_id', '=', self.env.user.company_id.id)])[0]

                payment_method = self.env['account.payment.method'].search([('code', '=', 'manual'),
                                                                            ('payment_type', '=', 'outbound')])[0]
                payment.journal_id = origin_id.id
                payment.destination_journal_id = destination_id.id
                payment.payment_method_id = payment_method.id

    @api.onchange('amount')
    def check_positive_value(self):
        """ La idea es que las cantidades que saquen a bancos siempre sea positiva """
        for payment in self:
            if payment.amount < 0:
                payment.amount = 0
                return {'warning': {
                                    'title': 'Advertencia!!',
                                    'message': 'No se pueden incluir cantidades negativas.',
                                    }
                            }
