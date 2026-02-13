# __author__ = 'BinhTT'
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class OnnetCustomer(models.Model):
    _inherit = 'res.partner'

    company_type = fields.Selection(selection_add=[('group', _('Is a Company Group'))])
    company_group = fields.Boolean(string='Is Company Group')
    group_type = fields.Selection(string='Group', selection=[('head', 'HEAD'), ('sub', 'SUB')],)
    parent_group_type = fields.Selection(string='Parent Group', related='parent_id.group_type')
    head_code = fields.Char(string='DO NOT USE')
    company_group_code = fields.Many2one('company.group', string='Company Group Code')
    head_id = fields.Many2one('res.partner', string='Head Company', )
    sub_ids = fields.One2many("res.partner", "head_id", "SUB List")
    promotion = fields.Many2one('coupon.program', string='Promotion Programs', )
    short_name_id = fields.Many2one(comodel_name='company.short.name', string="Short Name", copy=False)
    short_name = fields.Char(string='Short Name Char(Related)', related='short_name_id.name', copy=False)

    def update_short_name_id(self):
        model_short_name = self.env['company.short.name']
        partner_ids = self.sudo().env['res.partner'].search([])
        for r in partner_ids:
            if r.short_name_id:
                continue

                # r.short_name_id.id = self.get_company_short_name(r.company_group_code.name)
            r.write({'short_name_id': self.get_company_short_name(r.company_group_code.name if r.company_group_code else r.short_name)})
                # short_name_id = model_short_name.search([('name', '=', r.company_group_code.name)])
                # res = short_name_id or model_short_name.create({'name': r.company_group_code.name})


        return

    @api.onchange('short_name_id')
    def check_duplicate_short_name(self):
        if self.company_type == "group":
            return
        else:
            if self.short_name_id:
                short_name_num = len(self.search([('short_name_id', '=', self.short_name_id.id)]))
                if short_name_num > 0:
                    raise ValidationError("Code is existed!!")
        return

    # @api.depends('group_type', 'parent_id')
    # def check_company_group_code_condition(self):
    #     for r in self:
    #         r.invisible_company_group_code = True
    #         r.invisible_company_group_code_child = True
    #         if r.parent_id:
    #             continue
    #         if r.group_type != False and r.head_id:
    #             r.invisible_company_group_code_child = False
    #         else:
    #             r.invisible_company_group_code = False

    def create_short_name(self):
        partners = self.search([('short_name', '=', False)])
        for p in partners:
            if p.name:
                long_name = p.name.replace('CÔNG TY TNHH ', '')
                short_name = ''
                i = 0
                for split_name in long_name.split(' '):
                    if i > 2:
                        break
                    if not split_name:
                        continue
                    short_name += split_name[0].upper()
                    i += 1
                exist_partner = self.search([('short_name', 'like', short_name)], order='id desc', limit=1)
                if exist_partner:
                    exist_short_name = exist_partner.short_name.split('#')
                    number = 1
                    if len(exist_short_name) > 1:
                        number = int(exist_short_name[-1]) + 1
                    short_name += '#' + str(number)
                p.short_name_id = self.get_company_short_name(short_name)
        return

    #todo: check Head code unique
    @api.constrains('head_code')
    def constrain_head_code(self):
        if self.head_code and len(self.search([('head_code', '=', self.head_code), ('group_type', '=', 'head')])) > 1:
            raise UserError('Head Code is existed')

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
        if self and 'company_group_code' in vals:
            self.child_ids.write({'company_group_code': vals.get('company_group_code', False)})
            self.search([('head_id', 'in', self.ids)]).write({'company_group_code': vals.get('company_group_code', False)})
        res = super(OnnetCustomer, self).write(vals)

        return res

    def get_company_short_name(self, name=''):
        short_name_model = self.env['company.short.name']
        short_name_id = short_name_model.search([('name', '=', name)])
        res = short_name_id or short_name_model.create({'name': name})
        return res.id

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            company_group = val.get('company_group')
            if val.get('head_id', False):
                head_obi = self.browse(val.get('head_id', False))
                val.update({'company_group_code': head_obi.company_group_code.id or False,
                            'short_name_id': self.get_company_short_name(head_obi.company_group_code.name)})
            # if val.get('company_group_code', False):
            #     company_group_code = self.env['company.group'].browse(val.get('company_group_code', False))
            #     val.update({'short_name_id': self.get_company_short_name(company_group_code.name)})
            if not val.get('short_name', False):
                long_name = val.get('name').replace('CÔNG TY TNHH ', '')
                short_name = ''
                i = 0
                for split_name in long_name.split(' '):
                    if i > 2:
                        break
                    short_name += split_name[0].upper()
                    i += 1
                exist_short_name = self.env['company.short.name'].search([('name', 'like', short_name)], order='id desc', limit=1)
                exist_partner = self.search([('short_name_id', '=', exist_short_name.id)], order='id desc', limit=1)
                if exist_partner and exist_short_name and not company_group:
                    exist_short_name = exist_short_name.name.split('#')
                    number = 1
                    if len(exist_short_name) > 1:
                        number = int(exist_short_name[-1]) + 1
                    short_name += '#' + str(number)
                val.update(short_name_id=self.get_company_short_name(short_name))
                if company_group and not val.get('company_group_code', False):
                    company_group_obj = self.env['company.group'].search([('name', '=', short_name)]) \
                                        or self.env['company.group'].create({'name': short_name})
                    val.update(company_group_code=company_group_obj.id)
        res = super(OnnetCustomer, self).create(vals)
        return res
    
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(OnnetCustomer, self).fields_view_get(view_id, view_type, toolbar, submenu)
        return res