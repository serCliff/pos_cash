# -*- coding: utf-8 -*-

from odoo import models, fields, api
import pdb


class PosSession(models.Model):
    _inherit = 'pos.session'

    bank_amount = fields.Monetary("Transacciones Bancarias", help="Pedidos y facturas cobrados por bancos")

    daily_invoices_amount = fields.Monetary("Facturas a efectivo", compute="_compute_daily_invoices",
                                            help="Total cobrado en efectivo de facturas en el día")

    daily_invoices_amount_bank = fields.Monetary("Facturas a bancos", compute="_compute_daily_invoices",
                                            help="Total cobrado a través de bancos de facturas en el día")

    daily_invoices = fields.One2many("account.payment", "pos_invoice_transactions",
                                     string="Facturas del Día", help="Facturas cobradas en el día",
                                     domain=[('state', 'not in', ['draft','cancelled'])])

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

            # Transacciones de pagos en cash de facturas
            total_daily_cash = 0.0
            total_daily_bank = 0.0
            for payment_reg in session.daily_invoices:
                if payment_reg.payment_type == "inbound":
                    if payment_reg.journal_id.type == "cash":
                        total_daily_cash += payment_reg.amount
                    else:
                        total_daily_bank += payment_reg.amount
                else:
                    if payment_reg.journal_id.type == "cash":
                        total_daily_cash -= payment_reg.amount
                    else:
                        total_daily_bank -= payment_reg.amount

            session.daily_invoices_amount = total_daily_cash
            session.daily_invoices_amount_bank = total_daily_bank

            # Transacciones bancarias (salidas a bancos)
            session.external_transactions_amount = 0.0
            total_transactions = 0.0
            for transaction in session.external_transactions:
                total_transactions += transaction.amount
            session.external_transactions_amount = total_transactions

            # Actualizacion del diario de efectivo
            balance_external_transaction = total_transactions - total_daily_cash
            total_entry_encoding = sum(
                [line.amount for line in session.cash_register_id.line_ids])
            balance_end = session.cash_register_id.balance_start + total_entry_encoding \
                                                   - balance_external_transaction
            difference = session.cash_register_id.balance_end_real - balance_end

            session.cash_register_id.write({'balance_external_transaction': balance_external_transaction,
                                            'total_entry_encoding': total_entry_encoding,
                                            'balance_end': balance_end,
                                            'difference': difference})

            # Actualizacion del total facturado (daily_billing)
            session.daily_billing = session.cash_register_total_entry_encoding \
                                    + total_daily_cash \
                                    + total_daily_bank \
                                    + session.bank_amount \
                                    + session.external_transactions_amount

    @api.depends('config_id', 'statement_ids')
    def _compute_bank_journals(self):
        """
            Este metodo calcula el dinero que se ha cobrado a través de la caja en tarjeta, etc
            y se lo asigna a una variable para poder visualizarlo fácilmente.
        """
        # TODO: Borrar comentarios si no dan problemas
        for session in self:
            total_bank_amount = 0
            # total_daily_amount = 0
            for journal in session.statement_ids:
                if journal.journal_type == 'bank':
                    total_bank_amount += journal.total_entry_encoding
                # total_daily_amount += journal.total_entry_encoding
            session.bank_amount = total_bank_amount
            # session.daily_billing = total_daily_amount

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

    @api.multi
    def _get_opening_balance(self, journal_id):
        """
        Método sobre escrito para que busque específicamente la anterior caja de un usuario de la misma ciudad.
        :param journal_id:
        :return:
        """
        last_bnk_stmt = self.search([('journal_id', '=', journal_id),
                                     ('user_id.pos_id', '=', self.env.user.pos_id.id)],
                                    limit=1)
        if last_bnk_stmt:
            return last_bnk_stmt.balance_end
        return 0

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

