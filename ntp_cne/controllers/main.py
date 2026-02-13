import json
import logging
from odoo import http
from odoo.http import request


logger = logging.getLogger(__name__)


class TaxInvoiceController(http.Controller):
    @http.route(
        ["/ntp_cne/tax_invoice/webhook/<string:company_uuid>"],
        auth="public",
        type="json",
        methods=["POST"],
    )
    def bizzi_tax_invoice_create_webhook(self, company_uuid, **data):
        """
        Route to receive INVOICE.CREATED event from bizzi bot
        """
        logger.info("In bizzi_invoice_create_webhook controller")
        company = (
            request.env["res.company"]
            .sudo()
            .search([("tax_invoice_hook_id", "=", company_uuid)])
        )
        json_body = json.loads(request.httprequest.data)
        headers = request.httprequest.headers
        api_key_in_header = headers.get("X-API-KEY", None)
        if len(company) != 1:
            logger.error("bizzi_tax_invoice_create_webhook error !")
            logger.error("%d company found with uuid %s" % (len(company), company_uuid))
            return
        company = company[0]
        if not company.tax_invoice_integration:
            logger.error("bizzi_tax_invoice_create_webhook error !")
            logger.error(
                "company %s not enable tax_invoice_integration %s"
                % (company_uuid, company.tax_invoice_integration)
            )
            return
        # validate api-key
        if api_key_in_header != company.tax_invoice_hook_secret:
            logger.error("bizzi_tax_invoice_create_webhook error !")
            logger.error(
                "company %s request api-key %s not matched with company api-key %s"
                % (company_uuid, api_key_in_header, company.tax_invoice_hook_secret)
            )
            return
        # validate buyer_tax_code match with company.vat
        buyer_tax_code = json_body["payload"]["buyer_tax_code"]
        if buyer_tax_code != company.vat:
            logger.error("bizzi_tax_invoice_create_webhook error !")
            logger.error(
                f"buyer_tax_code '{buyer_tax_code}' not match with company vat number '{company.vat}' !"
            )
            return
        # insert to odoo
        tax_invoice_model = request.env["tax.invoice"].sudo()
        # # FIXME: dont know why but response from bizzi not have this info ??
        # payload = {"approval_status": ""}
        # payload.update(json_body['payload'])
        # event they push is not consistency, so instead of reading data in event message, we will read
        # by create another request to get info
        # tax_invoice_model.create_from_dict(payload)
        tax_invoice_model.create_from_invoice_id(json_body["payload"]["invoice_id"])
