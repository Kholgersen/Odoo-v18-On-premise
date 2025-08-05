odoo.define('pos_uala_pro.uala_pro_payment', function (require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');

    const UalaProPaymentScreen = (PaymentScreen) =>
        class extends PaymentScreen {
            async _finalizeValidation() {
                if (this.currentOrder.selected_paymentline.payment_method.is_uala_pro) {
                    // Aquí deberías mostrar un popup de espera y llamar al backend
                    try {
                        const response = await this.rpc({
                            model: 'pos.order',
                            method: '_process_payment_uala_pro',
                            args: [[], {
                                amount: this.currentOrder.selected_paymentline.amount,
                            }],
                        });
                        // Maneja la respuesta de la API de Ualá Pro
                        if (response.status === 'approved') {
                            // Continúa con el flujo normal
                        } else {
                            this.showPopup('ErrorPopup', {
                                title: 'Pago rechazado',
                                body: response.message || 'La transacción fue rechazada por Ualá Pro.',
                            });
                            return;
                        }
                    } catch (error) {
                        this.showPopup('ErrorPopup', {
                            title: 'Error de comunicación',
                            body: 'No se pudo procesar el pago con Ualá Pro.',
                        });
                        return;
                    }
                }
                await super._finalizeValidation();
            }
        };

    Registries.Component.extend(PaymentScreen, UalaProPaymentScreen);
});
