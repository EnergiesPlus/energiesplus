# coding: utf-8
# (c) AbAKUS IT Solutions
import logging
from pprint import pformat
import datetime
import jws
import requests
import json
from hashlib import sha256
from base64 import b64encode
from odoo import api, fields, models, _
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, float_round
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_payconiq.controllers.main import PayconiqController
from .mdetect import UAgentInfo

logging.captureWarnings(True)
_logger = logging.getLogger(__name__)

INT_CURRENCIES = [u'EUR']

EXT_URL_CONFIG = "https://ext.payconiq.com/certificates"
PROD_URL_CONFIG = "https://payconiq.com/certificates"

EXT_KID = "es.signature.ext.payconiq.com"
PROD_KID = "es.signature.payconiq.com"

PROD_URL_STRING = "prod"
EXT_URL_STRING = "ext"


class AcquirerPayconiq(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('payconiq', 'Payconiq')], ondelete={'payconiq': 'set default'})
    payconiq_merchantID = fields.Char('merchant_ID', default='',
                                      required_if_provider='payconiq', groups='base.group_user',
                                      help='Merchant ID provided by PayConiq')
    payconiq_secret_key = fields.Char('secret_key', default='',
                                      required_if_provider='payconiq', groups='base.group_user',
                                      help='Secret key provided by PayConiq')
    payconiq_callback_url = fields.Char('callback_url', default='https://my_odoo_site/payment/payconiq/callback',
                                        required_if_provider='payconiq', groups='base.group_user',
                                        help='Callback URL to provide to PayConiq')

    def _compute_callback(self):
        """ Dynamically build the callback url """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return "{}/{}".format(base_url, PayconiqController._callback_url)
    
    def _get_public_key_from_host(self, environment):
        _logger.info("Retrieving Public Key from the {} environment", environment)

        certificatesUrl = None
        keyId = None

        if(str(environment) == PROD_URL_STRING):
            certificatesUrl = PROD_URL_CONFIG
            keyId = PROD_KID
        elif(str(environment) == EXT_URL_STRING):
            certificatesUrl = EXT_URL_CONFIG
            keyId = EXT_KID
        #else:
            #throw new Exception("The environment provided must either be 'ext' or 'prod'")

        configCert = self._get_certificate_from_url(certificatesUrl, keyId)
        #return CryptoUtil.getPublicKeyFromCert(configCert);

    def _get_certificate_from_url(self, url, kid):
        response = requests.get(url)
        response_json = json.loads(response.text)
        return response_json['keys'][0]['x5c'][0]
    
    def _generate_signature(self, currency, amount, webhook_id):
        """ Payconiq signature generation method (sha256 encoded) """
        shasum = sha256()
        signature = '{merchant_id}{webhook_id}{currency}{amount}{secret_key}'.format(
            merchant_id=self.payconiq_merchantID,
            webhook_id=webhook_id,
            currency=currency,
            amount=amount,
            secret_key=self.payconiq_secret_key,
        )
        shasum.update(signature.encode('utf-8'))
        signature_encoded = b64encode(shasum.digest())
        return signature_encoded

    def payconiq_form_generate_values(self, values):
        """
        method that generates the values used to render the form button template.
        note: we store the SO in description field
        """
        self.ensure_one()
        # don't go any further if we don't have an SO yet and return values dict as payconiq_tx_values
        if values.get('reference') == '/':
            return dict(values)
        # we have a SO: let's request a transaction_id from Payconiq
        amount = int(values['amount'] * 100)
        currency = self.env['res.currency'].sudo().browse(values['currency_id']).name

        payconiq_tx_values = dict(values)
        payconiq_tx_values.update({
            'platform': self.get_platform(),
            'amount': amount,
            'currency': currency,
            'callbackUrl': self.payconiq_callback_url + "?webhookId=" + values.get('reference')
        })
        return payconiq_tx_values
    
    def payconiq_get_form_action_url(self):
        return '/payment/payconiq/pending'

    @staticmethod
    def get_platform():
        """ Use mdetect library to gess the calling platform """
        platform = 'android'
        headers = request.httprequest.headers
        user_agent = headers.get("User-Agent")
        http_accept = headers.get("Accept")
        if user_agent and http_accept:
            agent = UAgentInfo(userAgent=user_agent, httpAccept=http_accept)
            # Do first! For iPhone, iPod, iPad, etc.
            if agent.detectIos():
                platform = 'ios'
            elif not agent.detectMobileQuick():
                # if it is not a mobile device it is a web browser
                platform = 'web'
        return platform


class PaymentTxPayconiq(models.Model):
    _inherit = 'payment.transaction'
    # payconiq status
    _payconiq_pending_tx_status = ['PENDING']
    _payconiq_valid_tx_status = ['SUCCEEDED']
    _payconiq_failed_tx_status = ['FAILED']
    _payconiq_canceled_tx_status = ['CANCELLED', 'EXPIRED']
    
    def form_feedback(self, data, acquirer_name):
        return super(PaymentTxPayconiq, self).form_feedback(data, acquirer_name)

    def _payconiq_form_get_tx_from_data(self, data):
        """ Given a dict comming from Payconiq, verify it and find the related transaction record """
        # transaction reference is stored in the payconiq description
        _logger.debug("Payconiq: data={}".format(pformat(data, depth=4)))
        tx = self.search([('reference', '=', data.get('description'))])
        if not tx or len(tx) > 1:
            error_msg = _('Payconiq: received data for reference %s') % (data.get('description'))
            if not tx:
                error_msg += _('; no order found')
            else:
                error_msg += _('; multiple order found')
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # TODO: verify signature (done in header verification)
        if not tx.acquirer_reference:
            tx.acquirer_reference = data['paymentId']
        return tx

    def _payconiq_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        if data.get('amount') != int(self.amount * 100 if self.currency_id.name in INT_CURRENCIES else float_round(self.amount * 100, 2)):
            invalid_parameters.append(('Amount', data.get('amount'), self.amount * 100))
        if data.get('currency').upper() != self.currency_id.name:
            invalid_parameters.append(('Currency', data.get('currency'), self.currency_id.name))
        return invalid_parameters
    
    def _payconiq_form_validate(self, data):
        if self.state == 'done':
            # Payconiq: trying to validate an already validated tx (ref %s)', self.reference
            return True

        status = data.get('status')
        if status in self._payconiq_valid_tx_status:
            # SUCCEEDED
            self.write({
                'date': datetime.datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                'acquirer_reference': data['paymentId'],
            })
            self._set_transaction_done()
            return True
        elif status in self._payconiq_canceled_tx_status:
            # CANCELED or EXPIRED
            self.write({
                'acquirer_reference': data['paymentId'],
            })
            self._set_transaction_cancel()
            return False
        elif status in self._payconiq_pending_tx_status:
            # PENDING
            self.write({
                'acquirer_reference': data['paymentId'],
            })
            self._set_transaction_pending()
            return True
        else:
            # FAILED
            error = 'Payconiq: feedback error: %(error_str)s\n\n%(error_code)s: %(error_msg)s' % {
                'error_str': data.get('message', '-NO_MESSAGE-'),
                'error_code': data.get('code', '-NO_CODE-'),
                'error_msg':  "{}: {}".format(data.get('code', '-NO_CODE-'), data.get('message', '-NO_MESSAGE-')),
            }
            _logger.info(error)
            self.write({
                'state_message': error,
                'acquirer_reference': data['paymentId'],
            })
            self._set_transaction_error(error)
            return False
