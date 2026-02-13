import traceback
from pathlib import Path
from odoo import api, fields, models, _
from ..api.shinhanbank import ShinhanhBankExchangeRate


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("shinhanbank_vn", "Shinhan Bank VN")],
        ondelete={
            "shinhanbank_vn": "set default"
        },
    )

    def _parse_shinhanbank_vn_data(self, available_currencies):
        try:
            data = ShinhanhBankExchangeRate().get_current_exchange_rate()
            if not data:
                return False
            available_currency_names = available_currencies.mapped("name")
            odoo_data = {}
            for currency_code, rate in data.items():
                if currency_code in available_currency_names:
                    odoo_data[currency_code] = (1/rate, fields.Date.today())

            # odoo detect this as base currency of exchange rate
            if 'VND' in available_currency_names:
                odoo_data['VND'] = (1.0, fields.Date.today())
            return odoo_data
        except Exception as e:
            db_name = self._cr.dbname
            IrLogging = self.env['ir.logging']
            IrLogging.sudo().create({'name': 'ntp_currency_rate_live',
                    'type': 'server',
                    'dbname': db_name,
                    'level': 'ERROR',
                    'message': f"{e}\n{traceback.format_exc()}",
                    'path': str(Path(__file__).resolve()),
                    'func': '_parse_shinhanbank_vn_data',
                    'line': 1})
            return False
