# -*- coding: utf-8 -*-
{
    'name': "POS CASH",

    'summary': """
        Gestión mejorada del punto de venta para realizar el recuento de caja de toda la compañía.""",

    'description': """
        Gestión mejorada de cajas con el objetivo de revisar el efectivo y banco del día desde el punto venta
        Esto se hará independientemente de la forma en la que se registre dicho ingreso.
        
        Podremos contabilizar el dinero ingresado desde el punto de venta o desde el registro de pago de una factura.
        
        Permitirá gestionar salidas de efectivo de la caja a bancos.
        
        Mostrará de mejor manera la información económica del día.
    """,

    'author': "Sergio Del Castillo",
    'website': "http://www.sergiodelcastillo.com",


    'category': 'pos',
    'version': '0.3',

    # any module necessary for this one to work correctly
    'depends': ['point_of_sale', 'account', 'account_cancel', 'am_personalizations'],

    # always loaded
    'data': [
        'views/account_payment.xml',
        'views/pos_session.xml',
        'views/pos_config_kanban.xml',
        'views/res_users.xml',
    ],

}