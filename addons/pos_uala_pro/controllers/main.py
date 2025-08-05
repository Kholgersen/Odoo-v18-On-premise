from odoo import http
from odoo.http import request
import random
import time

UALA_PRO_ORDERS = {}

class UalaProController(http.Controller):
    @http.route('/pos_uala_pro/create_order', type='json', auth='user')
    def create_order(self, **kwargs):
        # Simulación: crear una orden y guardarla en memoria
        amount = kwargs.get('amount')
        order_id = f"uala_{random.randint(1000,9999)}_{int(time.time())}"
        UALA_PRO_ORDERS[order_id] = {
            'amount': amount,
            'status': 'waiting',
            'created': time.time(),
        }
        # Aquí iría la llamada real a la API de Ualá Pro
        return {'status': 'waiting', 'order_id': order_id}

    @http.route('/pos_uala_pro/check_status', type='json', auth='user')
    def check_status(self, order_id, **kwargs):
        # Simulación: después de 10 segundos, marcar como pagado
        order = UALA_PRO_ORDERS.get(order_id)
        if not order:
            return {'status': 'error', 'message': 'Orden no encontrada'}
        if order['status'] == 'paid':
            return {'status': 'paid'}
        # Simula pago automático tras 10 segundos
        if time.time() - order['created'] > 10:
            order['status'] = 'paid'
            return {'status': 'paid'}
        return {'status': 'waiting'}
