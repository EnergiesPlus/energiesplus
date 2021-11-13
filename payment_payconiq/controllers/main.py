# -*- coding: utf-8 -*-
# (c) 2018 AbAKAUS IT SOLUTIONS

import json
import logging
from werkzeug.utils import redirect
from odoo import http, _
from odoo.http import request
from odoo.addons.payment_payconiq.models.mdetect import UAgentInfo
import requests
import time
import werkzeug
import urllib

_logger = logging.getLogger(__name__)


class PayconiqController(http.Controller):
    _callback_url = '/payment/payconiq/callback'
    
    def _is_updated(self, reference):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        request_url = str(base_url) + "/payment/payconiq/feedback/get/" + str(reference)
        response = requests.post(request_url)
        if not response.text or str(response.text) in ['draft']:
            return False
        else:
            return True
    
    @http.route(['/payment/payconiq/feedback/<string:webhookId>'], type="http", auth="public", methods=['GET', 'POST'], website=True, csrf=False)
    def handle_payconiq_feedback(self, webhookId,**kw):
        while not self._is_updated(webhookId):
            time.sleep(2)
        return
    
    @http.route(['/payment/payconiq/feedback/get/<string:webhookId>'], type="http", auth="public", methods=['POST'], website=True, csrf=False)
    def handle_payconiq_feedback_get(self, webhookId,**kw):
        tx_id = request.env['payment.transaction'].sudo().search([("reference", '=', webhookId)], limit=1)
        return tx_id.state
        

    @http.route(['/payment/payconiq/callback'], type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def handle_payconiq_rogue_call(self, **args):
        """
        This code catches rogue calls made to Odoo by (we think) the PayConq iOS EXT App.
        We redirect to the actual confirmation endpoint/landing page
        """
        _default_response = '1'
        _logger.info("\n\n Rogue call")

        headers = request.httprequest.headers
        user_agent = headers.get("User-Agent")
        http_accept = headers.get("Accept")
        if user_agent and http_accept:
            agent = UAgentInfo(userAgent=user_agent, httpAccept=http_accept)
        else:
            agent = 'None'
        _logger.info("PAYCONIQ APP ROGUE CALL user_agent=(%s), http_accept=(%s), agent=(%s)" % (
            user_agent, http_accept, agent
        ))
        return redirect('/shop/confirmation', 301)

    @http.route(['/payment/payconiq/callback'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def handle_payconiq_callback(self, **post):
        """
        This code handles Payconiq merchant callback.
        The callback is a POST with regular JSON data and a custom security headers.
        { "_id": " 57dbc67db595282f 8bb95f eb",  "status": "SUCCEEDED" }
        The callback is not JSON RPC so we can not parse it with type=json in our Odoo routing.
        NOTE 1: A JSON RPC would have given us a json dict as post argument but implementation requires monkey patching
                Odoo in order to allow non JSON-RPC json to go through.
        NOTE 2: We will always send back the same response back to avoid phishing
        """
        _default_response = json.dumps({'status': 'DONE'}, separators=(',', ': '))
        if bool(post):
            # we received a JSON-RPC
            req_json = post
        else:
            # we received a flat JSON
            req_json = request.jsonrequest

        _logger.info("Payconiq: webhook called back with JSON=%s", req_json)
        transaction_id, status = req_json.get('paymentId'), req_json.get('status')
        if not transaction_id or not status:
            error_msg = _('Payconiq: missing transaction_id (%s) and/or status (%s)') % (transaction_id, status)
            _logger.warning(error_msg)
            return _default_response
        webhookId = request.httprequest.args.get('webhookId', None)
        if webhookId:
            # passes the Odoo Sale Order as webhookID -  /payment/payconiq/callback?webhookId=SO013
            response_json = json.loads(json.dumps({
                'description': webhookId,
                'paymentId': transaction_id,
                'status': status,
                'amount': req_json.get('totalAmount'),
                'currency': req_json.get('currency'),
            }))
        else:
            error_msg = _('Payconiq: missing webhookId for transaction (%s) and/or status (%s)') % (
                transaction_id, status
            )
            _logger.warning(error_msg)
            return _default_response

        # test our headers
        if not self.validate_callback_header(response_json):
            return _default_response

        request.env['payment.transaction'].sudo().form_feedback(response_json, 'payconiq')
        return _default_response

    @http.route(['/payment/payconiq/pending'], type='http', auth='public', methods=['GET', 'POST'], website=True, csrf=False)
    def pending_payment(self, **post):
        """ The pending payment page host the PayConiq widget used to perform payment.
        We need to be pointing to the proper REST API server depending on the environment we are in.
        Note that the only difference bewteen both JS script is the URL to the server.
        """
        website_id = request.website
        
        if not post.get('reference', False):
            return redirect('/shop/payment')
        
        payment_trx = request.env['payment.transaction'].sudo().search([('reference', '=', post['reference'])])
        payconiq = payment_trx.acquirer_id

        if payconiq.state == 'enabled':
            request_url = 'https://api.payconiq.com/v3/payments'
        elif payconiq.state == 'test':
            request_url = 'https://api.ext.payconiq.com/v3/payments'
            
        headers = {
            'Content-Type': 'application/json',
            'Authorization': payconiq.payconiq_secret_key
        }

        # Calculate the return url based on the current website.
        website_domain = str(request.env['ir.config_parameter'].sudo().get_param('web.base.url'))
        if website_id and website_id.domain:
            website_domain = website_id.domain
            while website_domain[-1] == '/':
                website_domain = website_domain[:-1]
                
        url = urllib.parse.urlparse(website_domain, 'https')
        if url.netloc:
            netloc = url.netloc
            path = url.path
        else:
            netloc = url.path
            path = ''
        url = url._replace(netloc=netloc, path=path)
        
        post['returnUrl']  = url.geturl() + "/payment/process"
        post['callbackUrl'] = payconiq.payconiq_callback_url + "?webhookId=" + post.get('reference')
        
        response = requests.post(request_url, headers=headers, json=post)
        post['response'] = json.loads(response.text)
        
        return http.request.render('payment_payconiq.pending_page', {'data': post})

    def validate_callback_header(self, data):
        """ Payconiq header signature validation """
        payconiq = request.env['payment.acquirer'].sudo().search([('provider', '=', 'payconiq')], limit=1)
        headers = request.httprequest.headers
        # Header check
        if 'Signature' not in headers:
            _logger.info('SECURITY: Missing signature')
            return False
        return True
