# -*- coding: utf-8 -*-

from odoo import models, api, fields

try:
    import requests
    import json
except ImportError:
    pass


class ResPartner(models.Model):
    _inherit = 'res.partner'

    autofill_from_vat = fields.Boolean()
    x_studio_legal_name_1 = fields.Char(string='Legal Name', tracking=True)

    @api.onchange('vat')
    def get_company_info_from_vat(self):
        if self.vat:
            url = 'https://thongtindoanhnghiep.co/api/company/' + self.vat
            res = requests.get(url, verify=True, )
            data = None
            if res.status_code == 200:
                data = json.loads(res.text)
                if data.get('ID') == 0:
                    return
            if data and 'ID' in data and data['ID'] is not None:
                self.name = self.name or data['TitleEn']
                self.x_studio_legal_name_1 = data['Title']
                self.street = self.street or data['DiaChiCongTy']
                self.city = self.city or data['TinhThanhTitle']
                results = self.env['res.country.state'].search([('country_id', '=', 241), \
                                                                ('name', '=', self.city)])
                self.state_id = self.state_id or results.id
                self.phone = self.phone  or data['NoiDangKyQuanLy_DienThoai']
                if 0 != data['ID']:
                    self.country_id = 241
                else:
                    self.country_id = self.country_id or False
                self.autofill_from_vat = True



    def create(self, vals_list):
        res = super(ResPartner, self).create(vals_list)
        if not self.env.context.get('create_invoice_add', False) and res.autofill_from_vat:
            res.with_context(create_invoice_add=True).create_invoice_add_from_vat()
        return res

    def create_invoice_add_from_vat(self):
        vals = {
            'type': 'invoice',
            'parent_id': self.id,
            'street': self.street,
            'city': self.city,
            'state_id': self.state_id.id,
            'phone': self.phone,
            'country_id': self.country_id.id,

        }
        self.create(vals)
        self.message_post(body='Created Invoice Address from VAT information')
        return

    def action_get_company_info_from_vat(self):
        for r in self:
            r.get_company_info_from_vat()
            if r.vat and not r.child_ids.filtered(lambda x:x.type == 'invoice'):
                r.create_invoice_add_from_vat()
            return r

    @api.model
    def update_partners_from_vat(self):
        self.search([('company_type', '=', 'company'), ('vat', '!=', False)]).action_get_company_info_from_vat()
        return {"type": "ir.actions.client", "tag": "reload"}