# -*- coding: utf-8 -*-
# Copyright (c) 2015-Present TidyWay Software Solution. (<https://tidyway.in/>)

from odoo import models, _
from odoo.exceptions import UserError


class ResetIncorrectMoves(models.TransientModel):
    _name = 'reset.incorrect.moves'
    _description = 'Reset Incorrect Moves'

    def bt_delete_incorrect_moves(self):
        self.ensure_one()
        if not self.env.user.has_group(
               'td_reset_stock_moves.group_delete_stock_moves'):
            raise UserError(_('You don"t have access permission to delete/hide '
                            'wrong moves, please contact to administrator!'))
        ctx = dict(self._context or {})
        move_obj = self.env['stock.move']
        Quant = self.env['stock.quant']
        Layer = self.env['stock.valuation.layer']
        move_ids = ctx.get('active_ids', []) or []
        for move_id in move_ids:
            move= move_obj.browse(move_id)
            move_before_delete = move.state
            move.move_line_ids.write({'state': 'draft'})
            move.move_line_ids.unlink()
            move.state = 'draft'
            if move.product_id.type == 'product' and move_before_delete != 'cancel':
                reset_qty = move.product_qty - move.reserved_availability
                #localtion to plus
                Quant._update_available_quantity(move.product_id,
                                                 move.location_id,
                                                 reset_qty)
                #dest localtion to minus
                Quant._update_available_quantity(move.product_id,
                                                 move.location_dest_id,
                                                 -reset_qty)
            layers = Layer.search([('stock_move_id', '=', move.id)])
            if layers:
                layers.sudo().unlink()
            move.unlink()

    def bt_cancel_incorrect_moves(self):
        self.ensure_one()
        if not self.env.user.has_group(
               'td_reset_stock_moves.group_delete_stock_moves'):
            raise UserError(_('You don"t have access permission to delete/hide '
                            'wrong moves, please contact to administrator!'))
        ctx = dict(self._context or {})
        move_obj = self.env['stock.move']
        Quant = self.env['stock.quant']
        Layer = self.env['stock.valuation.layer']
        move_ids = ctx.get('active_ids', []) or []
        total_moves = move_obj.browse(move_ids)
        for move in total_moves:
            move.move_line_ids.write({'state': 'draft'})
            move.move_line_ids.unlink()
            move.state = 'draft'
            if move.product_id.type == 'product':
                reset_qty = move.product_qty - move.reserved_availability
                #localtion to plus
                Quant._update_available_quantity(move.product_id,
                                                 move.location_id,
                                                 reset_qty)
                #dest localtion to minus
                Quant._update_available_quantity(move.product_id,
                                                 move.location_dest_id,
                                                 -reset_qty)
            layers = Layer.search([('stock_move_id', '=', move.id)])
            if layers:
                layers.sudo().unlink()
            move.state = 'cancel'

