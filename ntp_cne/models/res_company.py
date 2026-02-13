import logging
import time
from urllib.parse import urljoin
import uuid
import requests
from odoo import api, models, fields
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class CompanyTaxInvoiceIntegration(models.Model):
    _inherit = "res.company"

    tax_invoice_integration = fields.Boolean("Tax Invoice Integration")
    tax_invoice_last_succeeded_update = fields.Datetime("Last Succeeded Update Time")
    tax_invoice_hook_id = fields.Char(
        "Tax Invoice UUID Webhook",
        required=True,
        store=True,
        compute="_compute_tax_invoice_hook_id",
        help="Unique identifier to channel.",
    )
    tax_invoice_hook_secret = fields.Char(
        "Tax Invoice UUID Secret Key",
        required=True,
        store=True,
        default=lambda self: uuid.uuid4().hex,
        help="Unique identifier to channel.",
    )
    odoo_url = fields.Char(
        "Your URL",
        required=True,
        default=lambda x: x.env["ir.config_parameter"].sudo().get_param("web.base.url"),
        help="URL to receive messages. Don't use http://localhost",
    )
    tax_invoice_webhook_url = fields.Char(
        "Webhook URL", store=False, compute="_compute_tax_invoice_webhook_url"
    )

    def _compute_tax_invoice_hook_id(self):
        for rec in self:
            rec.tax_invoice_hook_id = uuid.uuid4().hex

    @api.depends("odoo_url", "tax_invoice_hook_id")
    def _compute_tax_invoice_webhook_url(self):
        for rec in self:
            rec.tax_invoice_webhook_url = False
            if rec.tax_invoice_integration:
                rec.tax_invoice_webhook_url = "%s/ntp_cne/tax_invoice/webhook/%s" % (
                    rec.odoo_url,
                    rec.tax_invoice_hook_id,
                )

    def action_update_tax_invoice_webhook(self):
        self.ensure_one()
        if not self.tax_invoice_integration:
            return
        # setup hook for bizzi
        get_param = self.env["ir.config_parameter"].sudo().get_param
        api_url = get_param("tax_invoice.tax_invoice_bizzi_api_url")
        api_key = get_param("tax_invoice.tax_invoice_bizzi_api_key")

        if not api_url or not api_key:
            raise UserError(
                "Please setup Api URL/Key in Settings > Accounting > Tax Invoice > Bizzi Config"
            )
        # get webhook / assume we config 1 vat number vs only 1 company in bizzi
        url = urljoin(api_url, "v1/companies")
        query_url = {"page": 1, "size": 20, "tax_code": self.vat}  # in res.company
        headers = {"accept": "application/json", "X-API-KEY": api_key}
        response = requests.get(url, params=query_url, headers=headers)
        # {
        #   "statusCode": 200,
        #   "data": [
        #     {
        #       "company_id": "d543a5b2-6fdb-47ee-88ad-ef188cf13b07",
        #       "name": "UAT _ CÔNG TY CỔ PHẦN NTP-TECH",
        #       "address": "Phòng 3503, Tòa W1 West Point, Đường Đỗ Đức Dục, Phường Mễ Trì, Quận Nam Từ Liêm, Thành phố Hà Nội, Việt Nam",
        #       "tax_code": "0108951191",
        #       "invoice_email": "uat_ntptech@dochoadon.com",
        #       "created_at": "2022-01-24T09:22:09.925734+00:00",
        #       "updated_at": "2022-01-24T09:22:09.925734+00:00"
        #     }
        #   ],
        #   "total": 1,
        #   "pagination": {
        #     "next": null,
        #     "prev": null,
        #     "first": "/v1/companies?page=1&size=20&tax_code=0108951191",
        #     "last": "/v1/companies?page=1&size=20&tax_code=0108951191"
        #   }
        # }
        bizzi_company_id = None
        if response.status_code == 200:
            bizzi_company_id = response.json()["data"][0]["company_id"]
        if bizzi_company_id:
            # webhook
            webhook_id = None
            # check webhook
            url = urljoin(api_url, "v1/webhooks")
            query_url = {"company_id": bizzi_company_id}
            response = requests.get(url, params=query_url, headers=headers)
            if response.status_code == 200:
                webhooks = response.json()["data"]
                for wh in webhooks:
                    # need to validate the webhook
                    # {
                    #   "statusCode": 200,
                    #   "data": [
                    #     {
                    #       "webhook_id": "4abe91eb-3ace-4fcd-b439-257ce329b01c",
                    #       "company_id": "d543a5b2-6fdb-47ee-88ad-ef188cf13b07",
                    #       "group_id": "b89c13c5-e6e1-4f7f-bb61-d19388fa868e",
                    #       "endpoint": "https://83ac-27-79-243-206.ngrok.io/ntp_cne/tax_invoice/webhook/10b85a9efd2c4eeabbb74761087f69a7",
                    #       "event_name": "INVOICE.CREATED",
                    #       "enable": true,
                    #       "headers": [
                    #         {
                    #           "key": "X-API-KEY",
                    #           "value": "32dd7ee3748f4e0c926ba8cfcf67c6b7"
                    #         }
                    #       ]
                    #     }
                    #   ]
                    # }
                    if (
                        wh["endpoint"] == self.tax_invoice_webhook_url
                        and wh["event_name"] == "INVOICE.CREATED"
                    ):
                        webhook_id = wh["webhook_id"]
                        break
            if not webhook_id:
                # config web hook
                url = urljoin(api_url, "v1/webhooks")
                json = {
                    "event_name": "INVOICE.CREATED",
                    "company_id": bizzi_company_id,
                    "endpoint": self.tax_invoice_webhook_url,
                    "enable": True,
                    "headers": [
                        {"key": "X-API-KEY", "value": self.tax_invoice_hook_secret}
                    ],
                }
                # FIXME: bizzi seems not allow for a too fast request to their server ?
                time.sleep(1)
                response = requests.post(url, json=json, headers=headers)
                if response.status_code == 201:
                    # TODO: need to show notification to user
                    self.tax_invoice_last_succeeded_update = fields.datetime.now()
                    logger.info("register webhook successfully ")
            else:
                # update api-key value for sure it work
                url = urljoin(api_url, f"v1/webhooks/{webhook_id}")
                json = {
                    "enable": True,
                    "headers": [
                        {"key": "X-API-KEY", "value": self.tax_invoice_hook_secret}
                    ],
                }
                time.sleep(1)
                response = requests.put(url, json=json, headers=headers)
                if response.status_code == 200:
                    # TODO: need to show notification to user
                    self.tax_invoice_last_succeeded_update = fields.datetime.now()
                    logger.info("update webhook successfully ")

    def action_get_tax_invoice_webhook_status(self):
        pass
