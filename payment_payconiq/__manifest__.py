# -*- coding: utf-8 -*-
# (c) AbAKUS IT Solutions
{
    'name': "Payconiq Payment Acquirer",
    'version': '14.0',
    'license': 'OPL-1',
    'author': 'ABAKUS IT-SOLUTIONS',
    'support': 'support@abakusitsolutions.eu',
    'category': 'Accounting/Payment',
    'website': "http://www.abakusitsolutions.eu",
    'depends': ['payment'],
    'data': [
        'views/payment_views.xml',
        'views/payment_payconiq_templates.xml',
        'views/pending_page.xml',
        'data/payment_acquirer_data.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'qweb': [
        'static/src/xml/payment_template.xml',    
    ],
    'external_dependencies': {
        'python': ['jws'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'price': 500,
    'currency': 'EUR',
}
