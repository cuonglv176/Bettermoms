# __author__ = 'BinhTT'
from odoo import models, fields, api, _
from odoo.exceptions import except_orm

class OnnetCustomer(models.Model):
    _inherit = 'res.partner'

    company_type = fields.Selection(selection_add=[('group', _('Is a Company Group'))])
    company_group = fields.Boolean(string='Is Company Group')
    group_type = fields.Selection(string='Group', selection=[('head', 'HEAD'), ('sub', 'SUB')],)
    head_code = fields.Char('Company Group Code')
    head_id = fields.Many2one('res.partner', string='Head Company', )
    promotion = fields.Many2one('coupon.program', string='Promotion Programs', )

    #todo: check Head code unique
    @api.constrains('head_code')
    def constrain_head_code(self):
        if self.head_code and len(self.search([('head_code', '=', self.head_code), ('group_type', '=', 'head')])) > 1:
            raise except_orm('Warning', 'Head Code is existed')

    @api.onchange('head_id')
    def onchange_head_id(self):
        if self.head_id and self.head_id.head_code:
            self.head_code = self.head_id.head_code

    @api.depends('company_group')
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = 'person'
            if partner.company_group:
                partner.company_type = 'group'
            elif partner.is_company:
                partner.company_type = 'company'

    def _write_company_type(self):
        super(OnnetCustomer, self)._write_company_type()
        for partner in self:
            partner.company_group = partner.company_type == 'group'

    #todo: do 3 if and overwrite function bcz self.company_type changed after check self.is_company or self.company_group
    @api.onchange('company_type')
    def onchange_company_type(self):
        if (self.company_type == 'company'):
            self.is_company = (self.company_type == 'company')
            self.company_group = False
        elif (self.company_type == 'group'):
            self.is_company = False
            self.company_group = True
        else:
            self.is_company = self.company_group = False

    def write(self, vals):
        if vals.get('company_type', False) and vals.get('company_type', '') != 'group':
            vals.update(company_group=False, head_code=False, head_id=False, group_type=False, promotion=False)
        res = super(OnnetCustomer, self).write(vals)
        return res