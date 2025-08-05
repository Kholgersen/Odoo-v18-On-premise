from odoo import models, fields

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_uala_pro = fields.Boolean("Ualá Pro Terminal")
