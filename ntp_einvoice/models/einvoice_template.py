import logging
from datetime import datetime
from odoo import api, fields, models, _
from ..utils.const import *


logger = logging.getLogger(__name__)


class EInvoiceTemplate(models.Model):
    _name = "ntp.einvoice.template"
    _description = "EInvoice Template"

    _sql_constraints = [
        (
            "name_uniq",
            "UNIQUE (name)",
            "You can not have two entries with the same name !",
        ),
        (
            "invoice_series_uniq",
            "UNIQUE (invoice_series)",
            "You can not have two entries with the same invoice_series !",
        ),
    ]

    company_id = fields.Many2one("res.company", "Company")

    name = fields.Char("Name", default="New", copy=False)
    code = fields.Char("Code")

    provider = fields.Selection(
        [
            ("sinvoice_v1", "S-Invoice v1"),
            ("sinvoice_v2", "S-Invoice v2"),
        ],
        "Provider",
        default="sinvoice_v2",
    )
    api_domain = fields.Char("API Domain")
    api_username = fields.Char("API Username")
    api_password = fields.Char("API Password")
    tax_code = fields.Char("Tax Code")

    invoice_type = fields.Selection(
        [
            ("vat_invoice", "VAT EInvoice"),
        ],
        default="vat_invoice",
    )
    invoice_template = fields.Char("Invoice Template")
    invoice_template_type = fields.Char("Invoice Template Type")
    invoice_series = fields.Char("Invoice Series", copy=False)

    is_default = fields.Boolean("Default")
    is_active = fields.Boolean("Active")

    last_synced = fields.Date(
        "Last Synced", default=datetime.strptime("01/01/1970", "%d/%m/%Y"), copy=False
    )

    def task_sync_einvoice_from_provider(self):
        for rec in self.env["ntp.einvoice.template"].search([]):
            try:
                if rec.is_active:
                    rec.do_sync_all()
            except Exception as e:
                logger.error(e, exc_info=True)

    def do_sync_all(self):
        self.ensure_one()
        from ..api import EInvoiceFactory

        factory = EInvoiceFactory.from_provider(self)
        invoices = factory.get_invoices(self.last_synced)
        invoice_no_list_in_db = (
            self.env["ntp.einvoice"]
            .with_context(active_test=False)
            .search([("einvoice_template_id", "=", self.id)])
            .mapped("name")
        )
        invoice_to_create = [
            invoice
            for invoice in invoices
            if invoice.invoice_no not in invoice_no_list_in_db
        ]
        data_to_create = []
        for invoice in invoice_to_create:
            try:
                buyer_type = BUYER_NOT_NEED_INVOICE
                if invoice.buyer_tax_code:
                    buyer_type = BUYER_COMPANY
                elif invoice.buyer_name:
                    buyer_type = BUYER_INDIVIDUAL
                data = {
                    "einvoice_template_id": self.id,
                    "issue_date": invoice.issue_date,
                    "name": invoice.invoice_no,
                    "currency_id": self.env["res.currency"]
                    .search([("name", "=", invoice.currency)])
                    .id,
                    "buyer_name": invoice.buyer_name,
                    "buyer_company_name": invoice.buyer_legal_name,
                    "buyer_address": invoice.buyer_address,
                    "buyer_phone_number": invoice.buyer_phone_number,
                    "buyer_tax_code": invoice.buyer_tax_code,
                    "buyer_type": buyer_type,
                    "payment_status": PAYMENT_STATUS_PAID
                    if invoice.payment_status == "paid"
                    else PAYMENT_STATUS_NOT_PAID_YET,
                    "provider_einvoice_status": invoice.status,
                }
                logger.info(f"New Invoice From Server: {invoice.invoice_no}")
                data_to_create.append(data)
            except Exception as e:
                logger.error(e)
        self.env["ntp.einvoice"].sudo().create(
            data_to_create
        )
        self.last_synced = fields.Date.today()

    def button_sync(self):
        self.do_sync_all()
