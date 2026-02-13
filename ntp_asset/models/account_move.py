# __author__ = 'BinhTT'
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

class AccountMove(models.Model):
    _inherit = 'account.move'


    def _auto_create_asset(self):
        create_list = []
        invoice_list = []
        auto_validate = []
        for move in self:
            if not move.is_invoice():
                continue
            if not move.line_ids.filtered(lambda line:line.tax_ids.filtered(lambda x: x.sum_create_asset)):
                return super()._auto_create_asset()
            vals = {}
            tax_msg = ''
            for move_line in move.line_ids.filtered(lambda line: not (move.move_type in ('out_invoice', 'out_refund') and line.account_id.user_type_id.internal_group == 'asset')):
                if (
                    move_line.account_id
                    and (move_line.account_id.can_create_asset)
                    and move_line.account_id.create_asset != "no"
                    and not move.reversed_entry_id
                    and not (move_line.currency_id or move.currency_id).is_zero(move_line.price_total)
                    and not move_line.asset_ids
                    and move_line.price_total > 0
                ):
                    if not move_line.name:
                        raise UserError(_('Journal Items of {account} should have a label in order to generate an asset').format(account=move_line.account_id.display_name))
                    if move_line.account_id.multiple_assets_per_line:
                        # decimal quantities are not supported, quantities are rounded to the lower int
                        units_quantity = max(1, int(move_line.quantity))
                    else:
                        units_quantity = 1
                    if not vals:
                        vals = {
                            'name': move_line.name,
                            'company_id': move_line.company_id.id,
                            'currency_id': move_line.company_currency_id.id,
                            'account_analytic_id': move_line.analytic_account_id.id,
                            'analytic_tag_ids': [(6, False, move_line.analytic_tag_ids.ids)],
                            'original_move_line_ids': [(6, False, move_line.ids)],
                            'state': 'draft',
                        }
                    if vals and move_line.tax_line_id:
                        vals.update({
                            'original_move_line_ids': vals.get('original_move_line_ids') + [(4, move_line.id)],
                        })
                        tax_msg += '<li>Tax Amount : %s</li>'%(abs(move_line.balance))
                        continue
                    model_id = move_line.account_id.asset_model
                    if model_id:
                        vals.update({
                            'model_id': model_id.id,
                        })
                    auto_validate.extend([move_line.account_id.create_asset == 'validate'] * units_quantity)
                    invoice_list.extend([move] * units_quantity)
                    for i in range(1, units_quantity + 1):
                        if units_quantity > 1:
                            vals['name'] = move_line.name + _(" (%s of %s)", i, units_quantity)
            if vals:
                create_list.extend([vals.copy()])

        assets = self.env['account.asset'].create(create_list)
        for asset, vals, invoice, validate in zip(assets, create_list, invoice_list, auto_validate):
            if 'model_id' in vals:
                asset._onchange_model_id()
                if validate:
                    asset.validate()
            if invoice:
                asset_name = {
                    'purchase': _('Asset'),
                    'sale': _('Deferred revenue'),
                    'expense': _('Deferred expense'),
                }[asset.asset_type]
                msg = _('%s created from invoice') % (asset_name)
                msg += ': <a href=# data-oe-model=account.move data-oe-id=%d>%s</a>' % (invoice.id, invoice.name)
                msg += tax_msg
                asset.message_post(body=msg)
        return assets
