# -*- coding: utf-8 -*-

from odoo import models, fields, api
import pdb


class ResUsers(models.Model):
    _inherit = "res.users"

    pos_id = fields.Many2one("pos.config", string="Punto de venta")
