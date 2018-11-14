# -*- coding: utf-8 -*-
from odoo import http

# class PosCash(http.Controller):
#     @http.route('/pos_cash/pos_cash/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pos_cash/pos_cash/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('pos_cash.listing', {
#             'root': '/pos_cash/pos_cash',
#             'objects': http.request.env['pos_cash.pos_cash'].search([]),
#         })

#     @http.route('/pos_cash/pos_cash/objects/<model("pos_cash.pos_cash"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pos_cash.object', {
#             'object': obj
#         })