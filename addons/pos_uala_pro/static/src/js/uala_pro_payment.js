odoo.define('pos_uala_pro.uala_pro_payment', function (require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');
    const { useState } = require('owl');

    const UalaProPaymentScreen = (PaymentScreen) =>
        class extends PaymentScreen {
            setup() {
                super.setup();
                this.ualaProState = useState({
                    status: 'idle', // idle, waiting, paid, error
                    order_id: null,
                });
            }

            get isUalaProSelected() {
                const line = this.currentOrder.selected_paymentline;
                return line && line.payment_method && line.payment_method.is_uala_pro;
            }

            async onUalaProClick() {
                this.ualaProState.status = 'waiting';
                try {
                    const response = await this.rpc({
                        route: '/pos_uala_pro/create_order',
                        params: {
                            amount: this.currentOrder.selected_paymentline.amount,
                        },
                    });
                    if (response.status === 'waiting') {
                        this.ualaProState.order_id = response.order_id;
                        this.pollUalaProStatus(response.order_id);
                    } else {
                        this.ualaProState.status = 'error';
                        this.showPopup('ErrorPopup', {
                            title: 'Error Ualá Pro',
                            body: response.message || 'No se pudo iniciar el pago.',
                        });
                    }
                } catch (error) {
                    this.ualaProState.status = 'error';
                    this.showPopup('ErrorPopup', {
                        title: 'Error de comunicación',
                        body: 'No se pudo conectar con Ualá Pro.',
                    });
                }
            }

            async pollUalaProStatus(order_id) {
                let attempts = 0;
                const poll = async () => {
                    if (this.ualaProState.status !== 'waiting') return;
                    try {
                        const resp = await this.rpc({
                            route: '/pos_uala_pro/check_status',
                            params: { order_id },
                        });
                        if (resp.status === 'paid') {
                            this.ualaProState.status = 'paid';
                            this.validateOrder();
                        } else if (attempts < 20) {
                            attempts++;
                            setTimeout(poll, 2000);
                        } else {
                            this.ualaProState.status = 'error';
                            this.showPopup('ErrorPopup', {
                                title: 'Tiempo de espera agotado',
                                body: 'No se recibió confirmación de pago.',
                            });
                        }
                    } catch (e) {
                        this.ualaProState.status = 'error';
                        this.showPopup('ErrorPopup', {
                            title: 'Error de comunicación',
                            body: 'No se pudo consultar el estado del pago.',
                        });
                    }
                };
                poll();
            }

            onUalaProCancel() {
                this.ualaProState.status = 'idle';
                this.ualaProState.order_id = null;
            }

            async validateOrder(isForceValidate) {
                if (this.isUalaProSelected) {
                    if (this.ualaProState.status !== 'paid') {
                        this.showPopup('ConfirmPopup', {
                            title: 'Pago pendiente',
                            body: 'Debes completar el pago en Ualá Pro antes de validar.',
                        });
                        return;
                    }
                }
                return super.validateOrder(isForceValidate);
            }
        };

    Registries.Component.extend(PaymentScreen, UalaProPaymentScreen);

    // Mostrar el botón de acción usando Owl template
    const { patch } = require('web.utils');
    const PaymentScreenComponent = require('point_of_sale.PaymentScreen');
    patch(PaymentScreenComponent.prototype, 'uala_pro_payment_button', {
        get ualaProButtonTemplate() {
            return this.isUalaProSelected ? 'uala_pro_payment.Button' : null;
        },
    });

    return PaymentScreen;
});
