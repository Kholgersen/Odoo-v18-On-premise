# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import xlsxwriter

class PricelistShareWizard(models.TransientModel):
    _name = 'pricelist.share.wizard'
    _description = 'Wizard to share price list with customers'
    
    pricelist_id = fields.Many2one('product.pricelist', string='Price List', required=True)
    partner_ids = fields.Many2many('res.partner', string='Customers', required=True,
                                  domain=[('customer_rank', '>', 0)])
    subject = fields.Char(string='Subject', required=True, 
                         default=lambda self: _('Price List: %s') % self.env.context.get('default_pricelist_name', ''))
    body = fields.Html(string='Message', required=True, 
                      default=lambda self: _("
                          <p>Hello,</p>
                          <p>Please find attached your custom price list.</p>
                          <p>Best regards,</p>
                      "))
    attachment_ids = fields.Many2many('ir.attachment', string='Additional Attachments')
    file_format = fields.Selection([
        ('excel', 'Excel'),
        ('pdf', 'PDF')
    ], string='File Format', default='excel', required=True)
    
    def action_send_pricelist(self):
        self.ensure_one()
        if not self.partner_ids:
            raise UserError(_('You must select at least one customer.'))
            
        # Generate attachment based on selected format
        if self.file_format == 'pdf':
            attachment = self._generate_pdf_attachment()
        else:  # excel
            attachment = self._generate_excel_attachment()
        
        # Add generated attachment to existing ones
        all_attachments = self.attachment_ids + attachment
        
        # Send email to each partner
        mail_template = self.env.ref('product.mail_template_pricelist_share', raise_if_not_found=False)
        for partner in self.partner_ids:
            email_values = {
                'subject': self.subject,
                'body_html': self.body,
                'email_to': partner.email,
                'attachment_ids': [(6, 0, all_attachments.ids)],
            }
            if mail_template:
                mail_template.send_mail(
                    self.pricelist_id.id,
                    force_send=True,
                    email_values=email_values
                )
            else:
                # fallback: send raw email
                self.env['mail.mail'].create({
                    'subject': self.subject,
                    'body_html': self.body,
                    'email_to': partner.email,
                    'attachment_ids': [(6, 0, all_attachments.ids)],
                }).send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Price list has been shared with %d customers.') % len(self.partner_ids),
                'sticky': False,
                'type': 'success',
            }
        }
    
    def _generate_pdf_attachment(self):
        """Generate PDF version of the pricelist"""
        report_action = self.env.ref('product.action_report_pricelist').report_action(self.pricelist_id)
        report = self.env['ir.actions.report']._render_qweb_pdf(report_action['report_name'], [self.pricelist_id.id])
        
        attachment_name = f"{self.pricelist_id.name} - Price List.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': attachment_name,
            'type': 'binary',
            'datas': base64.b64encode(report[0]),
            'res_model': 'product.pricelist',
            'res_id': self.pricelist_id.id,
        })
        
        return attachment
    
    def _generate_excel_attachment(self):
        """Generate Excel version of the pricelist"""
        pricelist = self.pricelist_id
        
        # Create an in-memory output file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(pricelist.name[:31])  # Excel sheet names limited to 31 chars
        
        # Add formatting
        header_format = workbook.add_format({
            'bold': True, 
            'align': 'center', 
            'valign': 'vcenter',
            'fg_color': '#D3D3D3', 
            'border': 1
        })
        cell_format = workbook.add_format({'border': 1})
        price_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        
        # Write headers
        headers = ['Product', 'List Price', f'Price ({pricelist.currency_id.name})', 'Discount']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Get all products
        products = self.env['product.product'].search([('active', '=', True)])
        
        # Write product data
        row = 1
        for product in products:
            list_price = product.list_price
            price = pricelist._get_product_price(product, 1.0, False)
            discount = 0
            if list_price > 0:
                discount = (list_price - price) / list_price * 100
                
            worksheet.write(row, 0, product.display_name, cell_format)
            worksheet.write(row, 1, list_price, price_format)
            worksheet.write(row, 2, price, price_format)
            worksheet.write(row, 3, f"{discount:.2f}%", cell_format)
            row += 1
            
        # Adjust column widths
        worksheet.set_column(0, 0, 40)  # Product column wider
        worksheet.set_column(1, 3, 15)  # Price columns
            
        workbook.close()
        
        # Create attachment
        attachment_name = f"{pricelist.name} - Price List.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': attachment_name,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'res_model': 'product.pricelist',
            'res_id': pricelist.id,
        })
        
        return attachment
