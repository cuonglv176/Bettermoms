class InvoiceTable():

    def __init__(self, odoo_env):
        self.env = odoo_env
        # key = sale_line_id.id
        self._table_data = []

    def _find_sale_line_id(self, sale_line_id):
        for id, (line_id, _) in enumerate(self._table_data):
            if line_id == sale_line_id:
                return id
        return None

    def add_sale_line_id(self, sale_line_id, quantity):
        _id = self._find_sale_line_id(sale_line_id)
        if not _id:
            self._table_data.append([sale_line_id, 0])
            _id = self._find_sale_line_id(sale_line_id)
        self._table_data[_id][1] += quantity

    def get_total_amount(self):
        total = 0
        for line_id, quantity in self._table_data:
            order_line = self.env['sale.order.line'].browse([line_id])
            price_unit_with_tax = order_line.price_total / order_line.product_uom_qty
            total += price_unit_with_tax * quantity
        return total

    def get_sale_line_ids(self):
        return self._table_data
