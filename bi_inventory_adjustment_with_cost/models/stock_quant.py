# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round, float_is_zero, pycompat


class StockQuantInherit(models.Model):
	_inherit = 'stock.quant'

	unit_price = fields.Float(readonly=False)
	inv_cost = fields.Boolean(related="company_id.inv_cost")
	

	@api.model
	def create(self, vals):
		""" Override to handle the "inventory mode" and create a quant as
		superuser the conditions are met.
		"""
		if self._is_inventory_mode() and any(f in vals for f in ['inventory_quantity', 'inventory_quantity_auto_apply']):
			allowed_fields = self._get_inventory_fields_create()
			if any(field for field in vals.keys() if field not in allowed_fields):
				raise UserError(_("Quant's creation is restricted, you can't do this operation."))

			inventory_quantity = vals.pop('inventory_quantity', False) or vals.pop(
				'inventory_quantity_auto_apply', False) or 0
			# Create an empty quant or write on a similar one.
			product = self.env['product.product'].browse(vals['product_id'])
			location = self.env['stock.location'].browse(vals['location_id'])
			lot_id = self.env['stock.production.lot'].browse(vals.get('lot_id'))
			package_id = self.env['stock.quant.package'].browse(vals.get('package_id'))
			owner_id = self.env['res.partner'].browse(vals.get('owner_id'))
			quant = self._gather(product, location, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=True)
			# unit_price = self.env['stock.quant'].browse(vals.get('unit_price'))
			

			if quant:
				quant = quant[0].sudo()
			else:
				quant = self.sudo().create(vals)
			# Set the `inventory_quantity` field to create the necessary move.
			quant.inventory_quantity = inventory_quantity
			quant.user_id = vals.get('user_id', self.env.user.id)
			quant.inventory_date = fields.Date.today()
			quant.unit_price = vals.pop('unit_price')
		

			

			return quant
		res = super(StockQuantInherit, self).create(vals)
		if self._is_inventory_mode():
			res._check_company()
		return res


	@api.model
	def _get_inventory_fields_create(self):
		return ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id','unit_price'] + self._get_inventory_fields_write()


	@api.model
	def default_get(self,fields):
		res = super(StockQuantInherit, self).default_get(fields)
		
	   
		if 'unit_price' in fields and res.get('product_id'):
			res['unit_price'] = self.env['product.product'].browse(res['product_id']).standard_price
		return res

	def _get_inventory_move_values(self, qty, location_id, location_dest_id,out=False):
		self.ensure_one()
		res = super(StockQuantInherit,self)._get_inventory_move_values(qty, location_id, location_dest_id, out)
 
		if fields.Float.is_zero(qty, 0, precision_rounding=self.product_uom_id.rounding):
			name = _('Product Quantity Confirmed')
		else:
			name = _('Product Quantity Updated')
		res.update({
		  'price_unit':self.unit_price
		})
		return res
