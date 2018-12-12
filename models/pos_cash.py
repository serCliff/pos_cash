# -*- coding: utf-8 -*-

from odoo import models, fields, api
import pdb


class PosSession(models.Model):
    _inherit = 'pos.session'

    bank_amount = fields.Monetary("Transacciones Bancarias", help="Pedidos y facturas cobrados por bancos")

    daily_invoices_amount = fields.Monetary("Efectivo facturas", compute="_compute_daily_invoices",
                                            help="Total cobrado en efectivo de facturas en el día")
    daily_invoices = fields.One2many("account.payment", "pos_invoice_transactions",
                                     string="Facturas del Día", help="Facturas cobradas en el día")

    external_transactions_amount = fields.Monetary("Salidas de Efectivo", compute="_compute_daily_invoices",
                                                   help="Total de salidas de efectivos a bancos")
    external_transactions = fields.One2many("account.payment", "pos_transactions",
                                            string="Resumen salidas a bancos",
                                            help="Crear para generar salida a bancos")

    daily_billing = fields.Monetary("TOTAL", compute="_compute_daily_invoices")

    bank_amount = fields.Monetary(
        compute="_compute_bank_journals",
        digits=0,
        string="Bank Transactions",
        help="Amount of bank journal transactions.",
        readonly=True)

    @api.onchange('external_transactions')
    def _compute_daily_invoices(self):
        """
        - Este metodo computa los valores que tienen que estar en cada uno de los fields.
        - En primer lugar computa el valor que suman los ingresos en efectivo de las facturas.
        - Después las salidas a bancos
        - Por último actualiza los valores que tienen que estar en el diario de caja para que
        se pueda cerrar la caja correctamente
        - Finalmente se calcula el final de los beneficios del día.

        """

        for session in self:
            session.daily_invoices_amount = 0

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
            balance_external_transaction = total_transactions - total_daily
            total_entry_encoding = sum(
                [line.amount for line in session.cash_register_id.line_ids])
            balance_end = session.cash_register_id.balance_start + total_entry_encoding \
                                                   - balance_external_transaction
            difference = session.cash_register_id.balance_end_real - balance_end

            session.cash_register_id.write({'balance_external_transaction': balance_external_transaction,
                                            'total_entry_encoding': total_entry_encoding,
                                            'balance_end': balance_end,
                                            'difference': difference})

            # Update daily billing
            session.daily_billing = session.cash_register_total_entry_encoding + total_daily
            session.daily_billing += sum([line.balance_end for line in session.statement_ids
                                          if line.journal_id.type != 'cash'])


    @api.depends('config_id', 'statement_ids')
    def _compute_bank_journals(self):
        """
            Este metodo calcula el dinero que se ha cobrado a través de la caja en tarjeta, etc
            y se lo asigna a una variable para poder visualizarlo fácilmente.
        """
        for session in self:
            total_bank_amount = 0
            total_daily_amount = 0
            for journal in session.statement_ids:
                if journal.journal_type == 'bank':
                    total_bank_amount += journal.total_entry_encoding
                total_daily_amount += journal.total_entry_encoding
            session.bank_amount = total_bank_amount
            session.daily_billing = total_daily_amount

    @api.multi
    def action_pos_session_validate(self):
        """
            En este método se van a validar las salidas a bancos para que queden correctamente computadas.
        """
        for session in self:
            # Validamos cada una de las transacciones a bancos que se han realizado desde el punto de venta
            for transaction in session.external_transactions:
                transaction.post()

        return super(PosSession, self).action_pos_session_validate()

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
        """
            Método que sobreescribe la validación de valores de la caja
            para sumar también las facturas y salidas a bancos
        """
        bnk_stmt_id = self.env.context.get('bank_statement_id', False) or self.env.context.get('active_id', False)
        bnk_stmt = self.env['account.bank.statement'].browse(bnk_stmt_id)
        total = 0.0
        for lines in self.cashbox_lines_ids:
            total += lines.subtotal

        pos_session = self.env['pos.session'].browse(self._context.get('active_id'))

        # Conteo de las transacciones externas y las facturas
        external_trans = pos_session.external_transactions_amount - pos_session.daily_invoices_amount
        if self.env.context.get('balance', False) == 'start':
            # starting balance
            bnk_stmt.write({'balance_start': total, 'balance_external_transaction': external_trans,
                            'cashbox_start_id': self.id})
        else:
            # closing balance
            bnk_stmt.write({'balance_end_real': total, 'balance_external_transaction': external_trans,
                            'cashbox_end_id': self.id})

        return {'type': 'ir.actions.act_window_close'}


