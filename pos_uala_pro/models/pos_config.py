from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    iface_uala_pro = fields.Boolean(
        string="Ualá Pro",
        help="Aceptar pagos con una terminal de pago Ualá Pro"
    )
    uala_pro_api_key = fields.Char("Ualá Pro API Key")
    uala_pro_terminal_id = fields.Char("Ualá Pro Terminal ID")
