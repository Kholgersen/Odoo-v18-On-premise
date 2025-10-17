from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    property_id = fields.Many2one('real.property', string='Propiedad asociada')

    def write(self, vals):
        res = super().write(vals)
        for product in self:
            if product.property_id:
                if product.id == product.property_id.sale_product_id.id:
                    product.property_id.list_price_sale = product.list_price
                elif product.id == product.property_id.rent_product_id.id:
                    product.property_id.list_price_rent = product.list_price
        return res