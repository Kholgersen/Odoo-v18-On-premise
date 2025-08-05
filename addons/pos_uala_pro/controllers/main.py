from odoo import http
from odoo.http import request

import random
import time
import requests

UALA_PRO_ORDERS = {}

class UalaProController(http.Controller):
    @http.route('/pos_uala_pro/create_order', type='json', auth='user')
    def create_order(self, **kwargs):
        # Obtener la configuración POS activa (puedes ajustar la lógica según tu flujo)
        pos_config = request.env['pos.config'].search([('iface_uala_pro', '=', True)], limit=1)
        if not pos_config:
            return {'status': 'error', 'message': 'No hay configuración POS con Ualá Pro activa'}

        # Obtener credenciales y entorno
        env = pos_config.uala_pro_env or 'test'
        if env == 'prod':
            base_url = 'https://checkout.developers.ar.ua.la/v2/api'
        else:
            base_url = 'https://checkout.stage.developers.ar.ua.la/v2/api'
        client_id = pos_config.uala_pro_client_id
        client_secret = pos_config.uala_pro_client_secret
        merchant_id = pos_config.uala_pro_merchant_id
        api_key = pos_config.uala_pro_api_key
        terminal_id = pos_config.uala_pro_terminal_id

        # Ejemplo de llamada real a la API de Ualá Pro
        amount = kwargs.get('amount')
        order_id = f"uala_{random.randint(1000,9999)}_{int(time.time())}"
        # Construir payload según documentación de Ualá Pro
        payload = {
            'amount': amount,
            'merchant_id': merchant_id,
            'terminal_id': terminal_id,
            # ...otros campos requeridos por la API...
        }
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        # Descomentar para llamada real:
        # try:
        #     response = requests.post(f"{base_url}/orders", json=payload, headers=headers, timeout=10)
        #     response.raise_for_status()
        #     api_result = response.json()
        #     # Procesar respuesta de Ualá Pro
        #     UALA_PRO_ORDERS[order_id] = {
        #         'amount': amount,
        #         'status': 'waiting',
        #         'created': time.time(),
        #         'uala_env': env,
        #         'uala_base_url': base_url,
        #         'uala_client_id': client_id,
        #         'uala_client_secret': client_secret,
        #         'uala_merchant_id': merchant_id,
        #         'uala_api_key': api_key,
        #         'uala_terminal_id': terminal_id,
        #         'uala_order_response': api_result,
        #     }
        #     return {'status': 'waiting', 'order_id': order_id, 'uala_env': env, 'uala_base_url': base_url, 'uala_order': api_result}
        # except Exception as e:
        #     return {'status': 'error', 'message': str(e)}

        # Simulación local (elimina esto cuando uses la API real)
        UALA_PRO_ORDERS[order_id] = {
            'amount': amount,
            'status': 'waiting',
            'created': time.time(),
            'uala_env': env,
            'uala_base_url': base_url,
            'uala_client_id': client_id,
            'uala_client_secret': client_secret,
            'uala_merchant_id': merchant_id,
            'uala_api_key': api_key,
            'uala_terminal_id': terminal_id,
        }
        return {'status': 'waiting', 'order_id': order_id, 'uala_env': env, 'uala_base_url': base_url}

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
