import base64

from odoo import api, fields, models, tools, _

from ..api.mst_finder import get_finder


class ResPartner(models.Model):
    _inherit = "res.partner"

    legal_name = fields.Char("Legal Name")

    def button_find_mst(self):
        self.ensure_one()
        if self.company_type == "individual":
            finder_type = "individual"
        else:
            finder_type = "company"
        finder = get_finder(self.env.user.id, finder_type, reset=True)
        image_url, image_data = finder.get_captcha()
        return {
            "type": "ir.actions.act_window",
            "name": "Find MST Info",
            "res_model": "mst.vn.finder.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.id,
                "default_user_id": self.env.user.id,
                "default_finder_type": finder_type,
                "default_tax_code": self.vat,
                "default_search_captcha": base64.b64encode(image_data),
                "default_search_captcha_url": image_url,
            },
        }
