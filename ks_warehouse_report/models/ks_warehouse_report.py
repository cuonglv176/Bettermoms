
from odoo import tools
from odoo import api, fields, models


class KSWarehouseReport(models.Model):
    _name = "ks.warehouse.report"
    _description = "Warehouse All in One Report"
    _auto = False
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _rec_name = 'date'
    # _order = 'date desc'

    id = fields.Integer('ID')
    ks_product_id = fields.Many2one('product.product', 'Product ID')
    ks_product_name = fields.Char('Product')
    ks_product_code = fields.Char('Product Code')
    ks_product_barcode = fields.Char('Product Barcode')
    ks_usage = fields.Selection([
        ('supplier', 'Vendor Location'),
        ('view', 'View'),
        ('internal', 'Internal Location'),
        ('customer', 'Customer Location'),
        ('inventory', 'Inventory Loss'),
        ('procurement', 'Procurement'),
        ('production', 'Production'),
        ('transit', 'Transit Location')], tracking=1)
    ks_product_type = fields.Selection([('product', 'Storable Product'),
                                     ('consu', 'Consumable'),
                                     ('service', 'Service')], tracking=1, string='Product Type')
    ks_product_categ_id = fields.Many2one('product.category', 'Category')
    ks_company_id = fields.Many2one('res.company', 'Company')
    ks_location_id = fields.Many2one('stock.location', 'Location')
    ks_product_sales_price = fields.Float('Sales Price')
    ks_product_qty_available = fields.Float('On Hand Qty')

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            ROW_NUMBER () OVER (ORDER BY pp.id) as id, 
            pp.id as ks_product_id, 
            pt.name as ks_product_name, 
            pp.default_code as ks_product_code, 
            pp.barcode as ks_product_barcode, 
            pt.type as ks_product_type, 
            pc.id as ks_product_categ_id, 
            pc.name as ks_category, 
            pt.list_price as ks_product_sales_price,
            sum(sq.quantity) as ks_product_qty_available, 
            sl.id as ks_location_id, 
            rc.id as ks_company_id,
            sl.usage as ks_usage
        """

        for field in fields.values():
            select_ += field

        from_ = """
                product_product as pp
                     LEFT JOIN product_template as pt ON pt.id = pp.product_tmpl_id
                     LEFT JOIN product_category as pc ON pc.id = pt.categ_id
                     LEFT JOIN stock_quant as sq ON sq.product_id = pp.id
                     LEFT JOIN stock_location as sl ON sl.id = sq.location_id
                     LEFT JOIN res_company as rc ON rc.id = sq.company_id %s
        """ % from_clause

        groupby_ = """
            pp.id, pt.name, pp.default_code, pp.barcode, pt.type, pc.id, pc.name, pt.list_price, sl.id, rc.id %s
        """ % groupby

        return "%s (SELECT %s FROM %s GROUP BY %s)" % (with_, select_, from_, groupby_)


    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
