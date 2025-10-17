from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class RealProperty(models.Model):
    _name = 'real.property'
    _description = 'Propiedad Inmobiliaria'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(string='Referencia', required=True, copy=False, default='Nuevo')
    street = fields.Char()
    city = fields.Char()
    province_id = fields.Many2one('res.country.state', string='Provincia')
    country_id = fields.Many2one('res.country', string='País')
    owner_id = fields.Many2one('res.partner', string='Propietario')
    description = fields.Text()
    list_price_sale = fields.Monetary(string='Precio de Venta')
    list_price_rent = fields.Monetary(string='Precio de Alquiler Mensual')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    area_m2 = fields.Float(string='Superficie (m²)')
    rooms = fields.Integer(string='Habitaciones')
    bathrooms = fields.Integer(string='Baños')
    state = fields.Selection([
        ('draft','Borrador'),
        ('available','Disponible'),
        ('reserved','Reservada'),
        ('rented','Alquilada'),
        ('sold','Vendida'),
        ('archived','Archivada')
    ], default='draft', tracking=True)

    sale_product_id = fields.Many2one('product.product', string='Producto Venta', ondelete='set null')
    rent_product_id = fields.Many2one('product.product', string='Producto Alquiler', ondelete='set null')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'El identificador de propiedad debe ser único.')
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            vals['name'] = self.env['ir.sequence'].next_by_code('real.property') or 'Nuevo'
        record = super().create(vals)
        record._ensure_related_products()
        return record

    def write(self, vals):
        res = super().write(vals)
        for prop in self:
            prop._sync_products_from_property()
        return res

    def _ensure_related_products(self):
        Product = self.env['product.product']
        for prop in self:
            if not prop.sale_product_id:
                prop.sale_product_id = Product.create({
                    'name': f"[Venta] {prop.name}",
                    'type': 'consu',
                    'list_price': prop.list_price_sale or 0.0,
                    'property_id': prop.id,
                    'description_sale': prop.description,
                })
            if not prop.rent_product_id:
                prop.rent_product_id = Product.create({
                    'name': f"[Alquiler] {prop.name}",
                    'type': 'service',
                    'list_price': prop.list_price_rent or 0.0,
                    'property_id': prop.id,
                    'description_sale': prop.description,
                })

    def _sync_products_from_property(self):
        for prop in self:
            if prop.sale_product_id:
                prop.sale_product_id.write({
                    'name': f"[Venta] {prop.name}",
                    'list_price': prop.list_price_sale or 0.0,
                    'description_sale': prop.description,
                })
            if prop.rent_product_id:
                prop.rent_product_id.write({
                    'name': f"[Alquiler] {prop.name}",
                    'list_price': prop.list_price_rent or 0.0,
                    'description_sale': prop.description,
                })