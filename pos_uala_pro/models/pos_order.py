import requests
from odoo import models

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _process_payment_uala_pro(self, payment_data):
        config = self.config_id
        api_key = config.uala_pro_api_key
        terminal_id = config.uala_pro_terminal_id
        amount = payment_data['amount']

        url = "https://api.ualabis.com.ar/v2/transactions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "terminal_id": terminal_id,
            "amount": amount,
            "currency": self.currency_id.name,
            "external_reference": self.pos_reference,
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
