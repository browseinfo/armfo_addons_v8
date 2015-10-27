# -*- coding: utf-8 -*-
##############################################################################
#
#    This module uses OpenERP, Open Source Management Solution Framework.
#    Copyright (C) 2014-Today BrowseInfo (<http://www.browseinfo.in>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

import time
import xmlrpclib
import email
import openerp
from openerp.addons.crm import crm
from openerp.osv import fields, osv, orm
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import html2plaintext
from openerp import tools, SUPERUSER_ID,api
from openerp.tools.mail import plaintext2html
import base64
import logging
from email.utils import formataddr
from urlparse import urljoin
from openerp.addons.base.ir.ir_mail_server import MailDeliveryException
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools import ustr
_logger = logging.getLogger(__name__)


from collections import OrderedDict
import xmlrpclib
from openerp.addons.mail.mail_message import decode


class crm_helpdesk(osv.osv):
    _inherit = 'crm.helpdesk'
    
#### TO CREATE NEW PARTNER FOR CRM HELPDESK REQUEST IF PARTNER IS UNKNOWN TO SYSTEM ###    
    
    def message_new(self, cr, uid, msg, custom_values=None, context=None):
        """ Overrides mail_thread message_new that is called by the mailgateway
            through message_process.
            This override updates the document according to the email.
        """
        if custom_values is None:
            custom_values = {}
        desc = html2plaintext(msg.get('body')) if msg.get('body') else ''
        Partner_obj = self.pool.get('res.partner')
        Fetchmail = self.pool.get('fetchmail.server')
        print 'message new of helpdesk',context,custom_values
        if msg.get('author_id') is False:
            vals = {
            'name' : msg.get('from').split('<')[0].strip(),
            'email' : msg.get('from').partition('<')[2].partition('>')[0].strip() or msg.get('from').split('<')[0].strip(),
            }
            partner = Partner_obj.create(cr, uid, vals)
        else:
            partner = msg.get('author_id', False)
        if context.get('fetchmail_server_id'):
            fetchmail_obj = Fetchmail.browse(cr, uid, context.get('fetchmail_server_id'))
### PARTNER FROM/REPLY FIELD FEED FROM FETCHMAIL SERVER #####
        part_from_replyto = ''
        if fetchmail_obj.email_sent_from and fetchmail_obj.email_sent_from.partition('<')[2].partition('>')[0].strip():
            
            partner_obj = Partner_obj.browse(cr, uid, partner)
            part_from_replyto = partner_obj.name + '<' + fetchmail_obj.email_sent_from.partition('<')[2].partition('>')[0].strip() + '>'
            
            print '\n create of helpdesk',part_from_replyto
        elif fetchmail_obj.email_sent_from:
            partner_obj = Partner_obj.browse(cr, uid, partner)
            part_from_replyto = partner_obj.name + '<' + fetchmail_obj.email_sent_from.strip() + '>'
#############################################################            
        defaults = {
            'name': msg.get('subject') or _("No Subject"),
#            'description': desc,
            'email_from': msg.get('from'),
            'email_cc': msg.get('cc'),
            'user_id': False,
            'partner_id': partner,
            'email_sent_from' : fetchmail_obj.email_sent_from,
            'email_reply_to' : fetchmail_obj.email_reply_to,
            'partner_from_replyto' : part_from_replyto,
        }
        defaults.update(custom_values)
        print 'message new ending ==',defaults
        return super(osv.Model, self).message_new(cr, uid, msg, custom_values=defaults, context=context)
        # defaults = {
        #     'name': msg.get('subject') or _("No Subject"),
        #     #'description': desc,
        #     'mail_description': desc,
        #     'email_from': msg.get('from'),
        #     'email_cc': msg.get('cc'),
        #     'user_id': False,
        #     'partner_id': partner,
        # }
        # defaults.update(custom_values)
        # return super(crm_helpdesk, self).message_new(cr, uid, msg, custom_values=defaults, context=context)
    
##################################################################################    
    
############## TO ADD PARTNER AS FOLLOWER ###############

    def create(self, cr, uid, vals, context=None):
        mail_followers_obj = self.pool.get('mail.followers')
        subtype_obj = self.pool.get('mail.message.subtype')
        context = dict(context or {})
        partner = vals.get('partner_id')
        new = set([partner])
        cre_id = super(crm_helpdesk, self).create(cr, uid, vals, context=context)
        subtype_ids = subtype_obj.search(
            cr, uid, [
                ('default', '=', True), '|', ('res_model', '=', self._name), ('res_model', '=', False)], context=context)
        mail_followers_obj.create(
            cr, SUPERUSER_ID, {
                'res_model': self._name,
                'res_id': cre_id,
                'partner_id': list(new)[0],
                'subtype_ids': [(6, 0, subtype_ids)],
            }, context=context)
       # self.pool.get('crm.helpdesk').message_subscribe(cr, uid, [cre_id], list(new), context=context)
        return cre_id
        
    def write(self, cr, uid, ids, values, context=None):
        Helpdesk_obj = self.pool.get('crm.helpdesk')
        old_partner_id = Helpdesk_obj.browse(cr, uid, ids).partner_id.id
        if values.get('partner_id'):
            partner = values.get('partner_id')
            new = set([partner])
            old = set([old_partner_id])
            Helpdesk_obj.message_unsubscribe(cr, uid, ids, list(old), context=context)
            Helpdesk_obj.message_subscribe(cr, uid, ids, list(new), context=context)
        return super(crm_helpdesk, self).write(cr, uid, ids, values, context=context)
        
#######################################################    

    def _new_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'draft'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _in_prog_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'open'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _pend_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'pending'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _close_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'done'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _canc_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'cancel'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res
        
    def _journal_item_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,{'journal_item_count': 0, 'contracts_count': 0}), ids))
        MoveLine = self.pool('account.move.line')
        AnalyticAccount = self.pool('account.analytic.account')
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        part_acc_move_line = len(MoveLine.search(cr, uid, [('partner_id', '=', hd_obj.partner_id.id)], context=context))
        part_anal_acc = len(AnalyticAccount.search(cr,uid, [('partner_id', '=', hd_obj.partner_id.id)], context=context))
        res[hd_obj.id]['journal_item_count'] = part_acc_move_line
        res[hd_obj.id]['contracts_count'] = part_anal_acc
        return res
        
             
    def _opportunity_meeting_phonecall_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,{'opportunity_count': 0, 'meeting_count': 0}), ids))
        # the user may not have access rights for opportunities or meetings
        try:
            for hd_obj in self.browse(cr, uid, ids, context):
                opp_ids = self.pool['crm.lead'].search(cr, uid, [('partner_id', '=', hd_obj.partner_id.id), ('type', '=', 'opportunity'), ('probability', '<', '100')], context=context)
                meeting_id = self.pool['calendar.event'].search(cr, uid, [('partner_ids', '=', hd_obj.partner_id.id)])
                res[hd_obj.id] = {
                    'opportunity_count': len(opp_ids),
                    'meeting_count': len(meeting_id),
                }
        except:
            pass
        for hd_obj in self.browse(cr, uid, ids, context):
            phone_id = self.pool['crm.phonecall'].search(cr, uid, [('partner_id', '=', hd_obj.partner_id.id)])
            res[hd_obj.id]['phonecall_count'] = len(phone_id)
        return res
    
    def _invoice_total(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        account_invoice_report = self.pool.get('account.invoice.report')
        for helpdesk in self.browse(cr, uid, ids, context=context):
            domain = [('partner_id', 'child_of', helpdesk.partner_id.id)]
            invoice_ids = account_invoice_report.search(cr, uid, domain, context=context)
            invoices = account_invoice_report.browse(cr, uid, invoice_ids, context=context)
            result[helpdesk.id] = sum(inv.user_currency_price_total for inv in invoices)
        return result
    
    def _sale_order_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))
        # The current user may not have access rights for sale orders
        try:
            for helpdesk in self.browse(cr, uid, ids, context):
                res[helpdesk.id] = len(helpdesk.partner_id.sale_order_ids)
        except:
            pass
        return res
    
    def _claim_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))       
        Claim = self.pool['crm.claim']
        for helpdesk in self.browse(cr, uid, ids, context):
            claim_ids = Claim.search(cr, uid, [('partner_id', '=', helpdesk.partner_id.id)])
            res[helpdesk.id] = len(claim_ids)
        return res
    
    def _issue_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))               
        Issue = self.pool['project.issue']
        for helpdesk in self.browse(cr, uid, ids, context):
            issue_ids = Issue.search(cr, uid, [('partner_id', '=', helpdesk.partner_id.id)])
            res[helpdesk.id] = len(issue_ids)
        return res

    def _task_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))                       
        Task = self.pool['project.task']
        for helpdesk in self.browse(cr, uid, ids, context):
            task_ids = Task.search(cr, uid, [('partner_id', '=', helpdesk.partner_id.id)])
            res[helpdesk.id] = len(task_ids)
        return res

    
    _columns = {
        'new_req_count': fields.function(_new_req_count, string='New', type='integer'),
        'mail_description': fields.text('Description'),
        'in_prog_req_count': fields.function(_in_prog_req_count, string='In Progress', type='integer'),
        'pend_req_count': fields.function(_pend_req_count, string='Pending', type='integer'),
        'close_req_count': fields.function(_close_req_count, string='Closed', type='integer'),
        'canc_req_count': fields.function(_canc_req_count, string='Cancelled', type='integer'),   
        'contracts_count': fields.function(_journal_item_count, string="Contracts", type='integer', multi="invoice_journal"),                
        'journal_item_count': fields.function(_journal_item_count, string="Journal Items", type="integer", multi="invoice_journal"),    
        'opportunity_count': fields.function(_opportunity_meeting_phonecall_count, string="Opportunity", type='integer', multi='opp_meet'),
        'meeting_count': fields.function(_opportunity_meeting_phonecall_count, string="Meetings", type='integer', multi='opp_meet'),
        'phonecall_count': fields.function(_opportunity_meeting_phonecall_count, string="Calls", type="integer", multi='opp_meet'), 
        'total_invoiced': fields.function(_invoice_total, string="Total Invoiced", type='float', groups='account.group_account_invoice'),
        'sale_order_count': fields.function(_sale_order_count, string='# of Sales Order', type='integer'),                               
        'claim_count': fields.function(_claim_count, string='# Claims', type='integer'),        
        'issue_count': fields.function(_issue_count, type='integer', string="Issues",),        
        'task_count': fields.function(_task_count, string='# Tasks', type='integer'),
        'section_id': fields.many2one('crm.case.section', 'Sales Team', \
                            select=True, help='Responsible sales team. Define Responsible user and Email account for mail gateway.'),
        'email_reply_to' : fields.char('Email Replyto', size=128),
        'email_sent_from' : fields.char('Email Sent From', size=128),
        'partner_from_replyto' : fields.char('Partner From/Replyto', size=128),
    }
    

class mail_notification(osv.Model):
    _inherit = 'mail.notification'
    
    def _notify_email(self, cr, uid, ids, message_id, force_send=False, user_signature=True, context=None):
        message = self.pool['mail.message'].browse(cr, SUPERUSER_ID, message_id, context=context)
        context.update({'default_res_id': message.res_id})
        print '\n mail notification of custom module',context,message_id,ids
        return super(mail_notification, self)._notify_email(cr, uid, ids, message_id, force_send=force_send, user_signature=True, context=context)
    
    
    def get_signature_footer(self, cr, uid, user_id, res_model=None, res_id=None, context=None, user_signature=True):
        """ Format a standard footer for notification emails (such as pushed messages
            notification or invite emails).
            Format:
                <p>--<br />
                    Administrator
                </p>
                <div>
                    <small>Sent from <a ...>Your Company</a> using <a ...>OpenERP</a>.</small>
                </div>
        """
        footer = ""
        if not user_id:
            return footer

        # add user signature
        user = self.pool.get("res.users").browse(cr, SUPERUSER_ID, [user_id], context=context)[0]
        if user_signature:
            if user.signature:
                signature = user.signature
            else:
                signature = "--<br />%s" % user.name
            footer = tools.append_content_to_html(footer, signature, plaintext=False)


#######################TO MAKE SIGNATURE UNCLICKABLE FOR CRM HELPDESK ##########################        
#        if (context.get('default_res_model') and context.get('default_res_model') == 'crm.helpdesk') or (context.get('default_model') and context.get('default_model') == 'crm.helpdesk'):
            
#            helpdesk_rec = self.pool.get('crm.helpdesk').browse(cr, uid, context.get('default_res_id'))
#            case_str = _('Ticket# %(id)s about Helpdesk %(Query)s')
#            case_string = '<br /><small>%s</small>' % (case_str % {
#            'id' : helpdesk_rec.id,
#            'Query' : helpdesk_rec.name})
#            
#            footer = tools.append_content_to_html(footer, case_string, plaintext=False, container_tag='div')
            
###############################################         
        else:
            # add company signature
            if user.company_id.website:
                website_url = ('http://%s' % user.company_id.website) if not user.company_id.website.lower().startswith(('http:', 'https:')) \
                    else user.company_id.website
                company = "<a style='color:inherit' href='%s'>%s</a>" % (website_url, user.company_id.name)
            else:
                company = user.company_id.name
            sent_by = _('Sent by %(company)s using %(odoo)s')
            signature_company = '<br /><small>%s</small>' % (sent_by % {
                'company': company,
                'odoo': "<a style='color:inherit' href='https://www.odoo.com/'>Odoo</a>"
            })
            footer = tools.append_content_to_html(footer, signature_company, plaintext=False, container_tag='div')


        return footer
        
    
class mail_mail(osv.Model):
    _inherit = 'mail.mail'
    
    def _get_partner_access_link(self, cr, uid, mail, partner=None, context=None):
        """ Generate URLs for links in mails:
            - partner is not an user: signup_url
            - partner is an user: fallback on classic URL
        """
        res = ""
        if context is None:
            context = {}
        partner_obj = self.pool.get('res.partner')
        if partner and not partner.user_ids:
            contex_signup = dict(context, signup_valid=True)
            signup_url = partner_obj._get_signup_url_for_action(cr, SUPERUSER_ID, [partner.id],
                                                                action='mail.action_mail_redirect',
                                                                model=mail.model, res_id=mail.res_id,
                                                                context=contex_signup)[partner.id]
#################### TO REMOVE CLICKABLE LINK FROM SIGNATURE FOR CRM HELPDESK ##################   
            if (context.get('default_model') == 'crm.helpdesk' and context.get('default_model') == 'crm.helpdesk') or (context.get('default_res_model') =='crm.helpdesk' and context.get('default_res_model') =='crm.helpdesk') or (context.get('thread_model') == 'crm.helpdesk' and context.get('thread_model') == 'crm.helpdesk') or (context.get('model_name') == 'Helpdesk' and context.get('model_name') == 'Helpdesk'):
                return res
#################################################################################################                
            else:
                return ", <span class='oe_mail_footer_access'><small>%(access_msg)s <a style='color:inherit' href='%(portal_link)s'>%(portal_msg)s</a></small></span>" % {
                    'access_msg': _('access directly to'),
                    'portal_link': signup_url,
                    'portal_msg': '%s %s' % (context.get('model_name', ''), mail.record_name) if mail.record_name else _('your messages '),
                }
        elif partner and partner.user_ids:
            base_url = self.pool.get('ir.config_parameter').get_param(cr, SUPERUSER_ID, 'web.base.url')
            mail_model = mail.model or 'mail.thread'
            url = urljoin(base_url, self.pool[mail_model]._get_access_link(cr, uid, mail, partner, context=context))
            
#########################################            
            if (context.get('default_model') == 'crm.helpdesk' and context.get('default_model') == 'crm.helpdesk') or (context.get('default_res_model') =='crm.helpdesk' and context.get('default_res_model') =='crm.helpdesk') or (context.get('thread_model') == 'crm.helpdesk' and context.get('thread_model') == 'crm.helpdesk') or (context.get('model_name') == 'Helpdesk' and context.get('model_name') == 'Helpdesk'):
                return res
###########################################                
            else:
                return "<span class='oe_mail_footer_access'><small>%(access_msg)s <a style='color:inherit' href='%(portal_link)s'>%(portal_msg)s</a></small></span>" % {
                    'access_msg': _('about') if mail.record_name else _('access'),
                    'portal_link': url,
                    'portal_msg': '%s %s' % (context.get('model_name', ''), mail.record_name) if mail.record_name else _('your messages'),
                }
                
        else:
            return None
            
    def send(self, cr, uid, ids, auto_commit=False, raise_exception=False, context=None):
        """ Sends the selected emails immediately, ignoring their current
            state (mails that have already been sent should not be passed
            unless they should actually be re-sent).
            Emails successfully delivered are marked as 'sent', and those
            that fail to be deliver are marked as 'exception', and the
            corresponding error mail is output in the server logs.

            :param bool auto_commit: whether to force a commit of the mail status
                after sending each mail (meant only for scheduler processing);
                should never be True during normal transactions (default: False)
            :param bool raise_exception: whether to raise an exception if the
                email sending process has failed
            :return: True
        """

        logging.info(context)
        context = dict(context or {})
        context['model_name'] = 'crm.helpdesk'
        print '\n in send mail',context,ids
        Helpdesk_pool = self.pool.get('crm.helpdesk')
        if context.get('default_res_model', False) == 'crm.helpdesk' or context.get('default_model', False) == 'crm.helpdesk' or context.get('thread_model', False) == 'crm.helpdesk' and 'default_res_id' in context:
            ir_mail_server = self.pool.get('ir.mail_server')
            ir_attachment = self.pool['ir.attachment']
######### TO ADD PARTNER NAME TO SENT FROM AND REPLY TO FIELD####### 
           
#            if context.get('add_partner') and context.get('default_res_id'):
#                vals = {}
#                helpdesk_obj = Helpdesk_pool.browse(cr, uid, context.get('default_res_id'))
#                print '\n in send mail with add_partner',helpdesk_obj.email_reply_to,helpdesk_obj.email_sent_from,helpdesk_obj.partner_id,helpdesk_obj.partner_id.name
#                if helpdesk_obj.email_reply_to and helpdesk_obj.email_reply_to.partition('<')[2].partition('>')[0].strip():
#                    vals.update({'email_reply_to' : helpdesk_obj.partner_id.name + '<' + helpdesk_obj.email_reply_to.partition('<')[2].partition('>')[0].strip() + '>'})
#                elif helpdesk_obj.email_reply_to:
#                    vals.update({'email_reply_to' : helpdesk_obj.partner_id.name + '<' + helpdesk_obj.email_reply_to.strip() + '>'})
                 
                
#                if helpdesk_obj.email_sent_from and helpdesk_obj.email_sent_from.partition('<')[2].partition('>')[0].strip():
#                    vals.update({'email_sent_from' : helpdesk_obj.partner_id.name + '<' + helpdesk_obj.email_sent_from.partition('<')[2].partition('>')[0].strip() + '>'})
#                elif helpdesk_obj.email_sent_from:
#                    vals.update({'email_sent_from' : helpdesk_obj.partner_id.name + '<' + helpdesk_obj.email_sent_from.strip() + '>'})
#                print '\n sent from and reply to',vals
#                Helpdesk_pool.write(cr, uid, context.get('default_res_id'), vals)
####################################################################     
       
            for mail in self.browse(cr, SUPERUSER_ID, ids, context=context):
                try:
                    # TDE note: remove me when model_id field is present on mail.message - done here to avoid doing it multiple times in the sub method
                    if mail.model:
                        model_id = self.pool['ir.model'].search(cr, SUPERUSER_ID, [('model', '=', mail.model)], context=context)[0]
                        model = self.pool['ir.model'].browse(cr, SUPERUSER_ID, model_id, context=context)
                    else:
                        model = None
                    if model:
                        context['model_name'] = model.name

                    # load attachment binary data with a separate read(), as prefetching all
                    # `datas` (binary field) could bloat the browse cache, triggerring
                    # soft/hard mem limits with temporary data.
                    attachment_ids = [a.id for a in mail.attachment_ids]
                    attachments = [(a['datas_fname'], base64.b64decode(a['datas']))
                                     for a in ir_attachment.read(cr, SUPERUSER_ID, attachment_ids,
                                                                 ['datas_fname', 'datas'])]

                    # specific behavior to customize the send email for notified partners
                    email_list = []
                    if mail.email_to:
                        email_list.append(self.send_get_email_dict(cr, uid, mail, context=context))
                    for partner in mail.recipient_ids:
                        email_list.append(self.send_get_email_dict(cr, uid, mail, partner=partner, context=context))
                    # headers
                    headers = {}
                    bounce_alias = self.pool['ir.config_parameter'].get_param(cr, uid, "mail.bounce.alias", context=context)
                    catchall_domain = self.pool['ir.config_parameter'].get_param(cr, uid, "mail.catchall.domain", context=context)
                    if bounce_alias and catchall_domain:
                        if mail.model and mail.res_id:
                            headers['Return-Path'] = '%s-%d-%s-%d@%s' % (bounce_alias, mail.id, mail.model, mail.res_id, catchall_domain)
                        else:
                            headers['Return-Path'] = '%s-%d@%s' % (bounce_alias, mail.id, catchall_domain)
                    if mail.headers:
                        try:
                            headers.update(eval(mail.headers))
                        except Exception:
                            pass

                    # Writing on the mail object may fail (e.g. lock on user) which
                    # would trigger a rollback *after* actually sending the email.
                    # To avoid sending twice the same email, provoke the failure earlier
                    mail.write({'state': 'exception'})
                    mail_sent = False
                    # build an RFC2822 email.message.Message object and send it without queuing
                    res = None
                    message_pool = self.pool.get('mail.message')
                    for email in email_list:
                        body = ''
                        if mail.mail_message_id.model == 'crm.helpdesk':
                            # start custom code for send mail from 'Email Sent From' field
                            helpdesk_obj = Helpdesk_pool.browse(cr, uid, context.get('default_res_id'), context=context)                        
                            # if context.get('default_res_id', False):
                            #     email_sub = ('['+'Case'+ ' ' + str(context.get('default_res_id'))+']') + ' '+ (helpdesk_obj.name)
                            email_from1 = ''
                            reply_to1 = ''
                            email_from1 = helpdesk_obj.email_sent_from
                            if helpdesk_obj.email_reply_to:
                                reply_to1 = helpdesk_obj.email_reply_to
                            else:
                                reply_to1 = helpdesk_obj.email_sent_from
                            print '\n send mail context',context
                            # crm_helpdesk_mails = self.pool.get('crm.helpdesk.emails').search(cr, uid, [])
                            # if crm_helpdesk_mails:
                            #     crm_helpdesk_browse = self.pool.get('crm.helpdesk.emails').browse(cr, uid, crm_helpdesk_mails[0])
                            #     email_from1 = crm_helpdesk_browse.sent_from or ''
                            #     if crm_helpdesk_browse.reply_to:
                            #         reply_to1 = crm_helpdesk_browse.reply_to
                            #     else:
                            #         reply_to1 = crm_helpdesk_browse.sent_from
                            
####################### TO SEND HISTORY TO NEW FOLLOWERS ######################       
                            if (context.get('history_mail') == True) or (context.get('invitation_mail') == True):
                                if context.get('history_mail') == True:
                                    print '\n in if condition of history mail',context
                                    history_body = ''
                                    message_ids = message_pool.search(cr, SUPERUSER_ID, [
                                        ('model', '=', mail.mail_message_id.model),
                                        ('res_id', '=', context.get('default_res_id')),
                                    ], context=context)
                                    
                                    for message_id in message_pool.browse(cr, uid, message_ids[1:], context=context):
                                        if message_id.type != 'notification':
                                            history_body += "<div style='margin:0 0 0 .8ex;border-left:1px #ccc solid;padding-left:1ex'><br><br>On %s " % message_id.date
                                            history_body += message_id.body + "</div>"
    #                                email.update({'body' : email.get('body') + ustr(body)})
                                    msg = ir_mail_server.build_email(
                                        email_from=helpdesk_obj.partner_from_replyto or False,
                                        email_to=email.get('email_to'),
                                        subject= helpdesk_obj.name,#email.get('subject'),
                                        body= ustr(history_body),
                                        body_alternative=email.get('body_alternative'),
                                        email_cc=tools.email_split(mail.email_cc),
                                        reply_to=helpdesk_obj.partner_from_replyto or False,
                                        attachments=attachments,
                                        message_id=mail.message_id,
                                        references=mail.references,
                                        object_id=mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                                        subtype='html',
                                        subtype_alternative='plain',
                                        headers=headers)
                                    try:
                                        #check for ir mail server if is it configure or not if not then take default
####### ADDED TO SPLIT MAIL ID FROM THE STRING ########################
                                        if helpdesk_obj.partner_from_replyto.partition('<')[2].partition('>')[0].strip():
                                            mail_frm = helpdesk_obj.partner_from_replyto.partition('<')[2].partition('>')[0].strip()
                                        else:
                                            mail_frm = helpdesk_obj.partner_from_replyto
##################################################################                            
                                        server_id = ir_mail_server.search(cr, uid, [('smtp_user','=', mail_frm)])
                                        if server_id:
                                            res = ir_mail_server.send_email(cr, uid, msg,
                                                                        mail_server_id=server_id,
                                                                        context=context)
                                        else:
                                            res = ir_mail_server.send_email(cr, uid, msg,
                                                                    mail_server_id=mail.mail_server_id.id,
                                                                    context=context)
                                    except AssertionError as error:
                                        if error.message == ir_mail_server.NO_VALID_RECIPIENT:
                                            # No valid recipient found for this particular
                                            # mail item -> ignore error to avoid blocking
                                            # delivery to next recipients, if any. If this is
                                            # the only recipient, the mail will show as failed.
                                            _logger.warning("Ignoring invalid recipients for mail.mail %s: %s",
                                                            mail.message_id, email.get('email_to'))
                                        else:
                                            raise
                                            
##################### HISTORY MAIL TO NEW FOLLOWERS SEND ###################### 

########################## To send invitation mail ############################

                                if context.get('invitation_mail') == True:
                                    print '\n in if condition of invitation mail',context
                                    msg = ir_mail_server.build_email(
                                        email_from=helpdesk_obj.partner_from_replyto or False,
                                        email_to=email.get('email_to'),
                                        subject= email.get('subject'),
                                        body= email.get('body'),
                                        body_alternative=email.get('body_alternative'),
                                        email_cc=tools.email_split(mail.email_cc),
                                        reply_to=helpdesk_obj.partner_from_replyto or False,
                                        attachments=attachments,
                                        message_id=mail.message_id,
                                        references=mail.references,
                                        object_id=mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                                        subtype='html',
                                        subtype_alternative='plain',
                                        headers=headers)
                                    try:
                                        #check for ir mail server if is it configure or not if not then take default
################### ADDED TO SPLIT MAIL ID FROM THE STRING ###################
                                        if helpdesk_obj.partner_from_replyto.partition('<')[2].partition('>')[0].strip():
                                            mail_frm = helpdesk_obj.partner_from_replyto.partition('<')[2].partition('>')[0].strip()
                                        else:
                                            mail_frm = helpdesk_obj.partner_from_replyto
##################################################################                            
                                        server_id = ir_mail_server.search(cr, uid, [('smtp_user','=', mail_frm)])
                                        if server_id:
                                            res = ir_mail_server.send_email(cr, uid, msg,
                                                                        mail_server_id=server_id,
                                                                        context=context)
                                        else:
                                            res = ir_mail_server.send_email(cr, uid, msg,
                                                                    mail_server_id=mail.mail_server_id.id,
                                                                    context=context)
                                    except AssertionError as error:
                                        if error.message == ir_mail_server.NO_VALID_RECIPIENT:
                                            # No valid recipient found for this particular
                                            # mail item -> ignore error to avoid blocking
                                            # delivery to next recipients, if any. If this is
                                            # the only recipient, the mail will show as failed.
                                            _logger.warning("Ignoring invalid recipients for mail.mail %s: %s",
                                                            mail.message_id, email.get('email_to'))
                                        else:
                                            raise

################### invitation mail send ##################
                            else:
####### TO APPEND HISTORY TO MAIL FROM HELPDESK RECORD ###########
                                message_pool = self.pool.get('mail.message')
                                message_ids = message_pool.search(cr, SUPERUSER_ID, [
                                    ('model', '=', mail.mail_message_id.model),
                                    ('res_id', '=', context.get('default_res_id')),
                                ], context=context)
                                body = ''
                                print '\n in else of history mail'
                                for message_id in message_pool.browse(cr, uid, message_ids[1:], context=context):
                                    if message_id.type != 'notification':
                                        body += "<div style='margin:0 0 0 .8ex;border-left:1px #ccc solid;padding-left:1ex'><br><br>On %s " % message_id.date
                                        body += message_id.body + "</div>"
                                        
                                email.update({'body' : email.get('body') + ustr(body)})

####################################################################
                                if context.get('partner_reply') and context.get('default_res_id'):
                                    helpdesk_obj = Helpdesk_pool.browse(cr, uid, context.get('default_res_id'))
                                    email_from1 = helpdesk_obj.partner_from_replyto
                                    reply_to1 = helpdesk_obj.partner_from_replyto
                                
                                msg = ir_mail_server.build_email(
                                    email_from=email_from1,
                                    email_to=email.get('email_to'),
                                    subject= email.get('subject'),
                                    body= email.get('body'),
                                    body_alternative=email.get('body_alternative'),
                                    email_cc=tools.email_split(mail.email_cc),
                                    reply_to=reply_to1,
                                    attachments=attachments,
                                    message_id=mail.message_id,
                                    references=mail.references,
                                    object_id=mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                                    subtype='html',
                                    subtype_alternative='plain',
                                    headers=headers)
                                try:
                                    #check for ir mail server if is it configure or not if not then take default
################### ADDED TO SPLIT MAIL ID FROM THE STRING ##########
                                    if email_from1.partition('<')[2].partition('>')[0].strip():
                                        mail_frm = email_from1.partition('<')[2].partition('>')[0].strip()
                                    else:
                                        mail_frm = email_from1
##################################################################                            
                                    server_id = ir_mail_server.search(cr, uid, [('smtp_user','=', mail_frm)])
                                    if server_id:
                                        res = ir_mail_server.send_email(cr, uid, msg,
                                                                    mail_server_id=server_id,
                                                                    context=context)
                                    else:
                                        res = ir_mail_server.send_email(cr, uid, msg,
                                                                mail_server_id=mail.mail_server_id.id,
                                                                context=context)
                                except AssertionError as error:
                                    if error.message == ir_mail_server.NO_VALID_RECIPIENT:
                                        # No valid recipient found for this particular
                                        # mail item -> ignore error to avoid blocking
                                        # delivery to next recipients, if any. If this is
                                        # the only recipient, the mail will show as failed.
                                        _logger.warning("Ignoring invalid recipients for mail.mail %s: %s",
                                                        mail.message_id, email.get('email_to'))
                                    else:
                                        raise

                                
##########################################################################                                
                        else:
                            email_from1 = mail.email_from
                            reply_to1 = mail.reply_to
                        
                        
#################TO CHANGE SUBJECT FOR HELPDESK ################
                            msg = ir_mail_server.build_email(
                                email_from=email_from1,
                                email_to=email.get('email_to'),
                                subject= email.get('subject'),
                                body= email.get('body'),
                                body_alternative=email.get('body_alternative'),
                                email_cc=tools.email_split(mail.email_cc),
                                reply_to=reply_to1,
                                attachments=attachments,
                                message_id=mail.message_id,
                                references=mail.references,
                                object_id=mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                                subtype='html',
                                subtype_alternative='plain',
                                headers=headers)
                            try:
                                #check for ir mail server if is it configure or not if not then take default
################### ADDED TO SPLIT MAIL ID FROM THE STRING #########################
                                if email_from1.partition('<')[2].partition('>')[0].strip():
                                    mail_frm = email_from1.partition('<')[2].partition('>')[0].strip()
                                else:
                                    mail_frm = email_from1
##################################################################                            
                                server_id = ir_mail_server.search(cr, uid, [('smtp_user','=', mail_frm)])
                                if server_id:
                                    res = ir_mail_server.send_email(cr, uid, msg,
                                                                mail_server_id=server_id,
                                                                context=context)
                                else:
                                    res = ir_mail_server.send_email(cr, uid, msg,
                                                            mail_server_id=mail.mail_server_id.id,
                                                            context=context)
                            except AssertionError as error:
                                if error.message == ir_mail_server.NO_VALID_RECIPIENT:
                                    # No valid recipient found for this particular
                                    # mail item -> ignore error to avoid blocking
                                    # delivery to next recipients, if any. If this is
                                    # the only recipient, the mail will show as failed.
                                    _logger.warning("Ignoring invalid recipients for mail.mail %s: %s",
                                                    mail.message_id, email.get('email_to'))
                                else:
                                    raise
                    if res:
                        mail.write({'state': 'sent', 'message_id': res})
                        mail_sent = True

                    # /!\ can't use mail.state here, as mail.refresh() will cause an error
                    # see revid:odo@openerp.com-20120622152536-42b2s28lvdv3odyr in 6.1
                    if mail_sent:
                        _logger.info('Mail with ID %r and Message-Id %r successfully sent', mail.id, mail.message_id)
                    self._postprocess_sent_message(cr, uid, mail, context=context, mail_sent=mail_sent)
                except MemoryError:
                    # prevent catching transient MemoryErrors, bubble up to notify user or abort cron job
                    # instead of marking the mail as failed
                    _logger.exception('MemoryError while processing mail with ID %r and Msg-Id %r. '\
                                          'Consider raising the --limit-memory-hard startup option',
                                      mail.id, mail.message_id)
                    raise
                except Exception as e:
                    _logger.exception('failed sending mail.mail %s', mail.id)
                    mail.write({'state': 'exception'})
                    self._postprocess_sent_message(cr, uid, mail, context=context, mail_sent=False)
                    if raise_exception:
                        if isinstance(e, AssertionError):
                            # get the args of the original error, wrap into a value and throw a MailDeliveryException
                            # that is an except_orm, with name and value as arguments
                            value = '. '.join(e.args)
                            raise MailDeliveryException(_("Mail Delivery Failed"), value)
                        raise

                if auto_commit is True:
                    cr.commit()
            return True
        return super(mail_mail, self).send(cr, uid, ids, auto_commit, raise_exception, context=context)
    
# class crm_helpdesk_emails(osv.osv):
#     _name = 'crm.helpdesk.emails'
#     _columns = {
#             'sent_from': fields.char('Email Sent From'),
#             'reply_to': fields.char('Reply To'),
#             'model_id':fields.many2one('ir.model','Model')
#     }


class res_partner(osv.osv):
    _inherit = 'res.partner'
    def _Helpdesk_count(self, cr, uid, ids, field_name, arg, context=None):
        Helpdesks = self.pool['crm.helpdesk']
        return {
            partner_id: Helpdesks.search_count(cr,uid, [('partner_id', '=', partner_id)], context=context)  
            for partner_id in ids
        }

    _columns = {
        'helpdesk_count': fields.function(_Helpdesk_count, string='# Helpdesks', type='integer'),
    }
    

class mail_thread(osv.AbstractModel):
    _inherit = 'mail.thread'    
    
    def message_process(self, cr, uid, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None, context=None):
        """ Process an incoming RFC2822 email message, relying on
            ``mail.message.parse()`` for the parsing operation,
            and ``message_route()`` to figure out the target model.

            Once the target model is known, its ``message_new`` method
            is called with the new message (if the thread record did not exist)
            or its ``message_update`` method (if it did).

            There is a special case where the target model is False: a reply
            to a private message. In this case, we skip the message_new /
            message_update step, to just post a new message using mail_thread
            message_post.

           :param string model: the fallback model to use if the message
               does not match any of the currently configured mail aliases
               (may be None if a matching alias is supposed to be present)
           :param message: source of the RFC2822 message
           :type message: string or xmlrpclib.Binary
           :type dict custom_values: optional dictionary of field values
                to pass to ``message_new`` if a new record needs to be created.
                Ignored if the thread record already exists, and also if a
                matching mail.alias was found (aliases define their own defaults)
           :param bool save_original: whether to keep a copy of the original
                email source attached to the message after it is imported.
           :param bool strip_attachments: whether to strip all attachments
                before processing the message, in order to save some space.
           :param int thread_id: optional ID of the record/thread from ``model``
               to which this mail should be attached. When provided, this
               overrides the automatic detection based on the message
               headers.
        """
        if context is None:
            context = {}
        print 'in message process of helpdesk',context,thread_id
        # extract message bytes - we are forced to pass the message as binary because
        # we don't know its encoding until we parse its headers and hence can't
        # convert it to utf-8 for transport between the mailgate script and here.
        if isinstance(message, xmlrpclib.Binary):
            message = str(message.data)
        # Warning: message_from_string doesn't always work correctly on unicode,
        # we must use utf-8 strings here :-(
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        msg_txt = email.message_from_string(message)

        # parse the message, verify we are not in a loop by checking message_id is not duplicated
        msg = self.message_parse(cr, uid, msg_txt, save_original=save_original, context=context)
        
        if strip_attachments:
            msg.pop('attachments', None)

        if msg.get('message_id'):   # should always be True as message_parse generate one if missing
            existing_msg_ids = self.pool.get('mail.message').search(cr, SUPERUSER_ID, [
                                                                ('message_id', '=', msg.get('message_id')),
                                                                ], context=context)
            if existing_msg_ids:
                _logger.info('Ignored mail from %s to %s with Message-Id %s: found duplicated Message-Id during processing',
                                msg.get('from'), msg.get('to'), msg.get('message_id'))
                return False

        # find possible routes for the message
        routes = self.message_route(cr, uid, msg_txt, msg, model, thread_id, custom_values, context=context)
        thread_id = self.message_route_process(cr, uid, msg_txt, msg, routes, context=context)
        print '\n in message process of helpdesk bfr state change',thread_id
        if routes[0][0] == 'crm.helpdesk' and msg.get('parent_id'):
            Helpdesk_obj = self.pool.get('crm.helpdesk')
            hd_rec = Helpdesk_obj.browse(cr, uid, routes[0][1])
            if hd_rec.state in ['draft', 'pending', 'done', 'cancel']:
                Helpdesk_obj.write(cr, uid, routes[0][1], {'state' : 'open'})
        return thread_id    


    def message_route_process(self, cr, uid, message, message_dict, routes, context=None):
        # postpone setting message_dict.partner_ids after message_post, to avoid double notifications
        context = dict(context or {})
        partner_ids = message_dict.pop('partner_ids', [])
        thread_id = False
        Mail_message_pool = self.pool.get('mail.message')
        print '\n message route helpdes',context,message_dict,routes
        for model, thread_id, custom_values, user_id, alias in routes:
            if self._name == 'mail.thread':
                context['thread_model'] = model
            if model:
                model_pool = self.pool[model]
                if not (thread_id and hasattr(model_pool, 'message_update') or hasattr(model_pool, 'message_new')):
                    raise ValueError(
                        "Undeliverable mail with Message-Id %s, model %s does not accept incoming emails" %
                        (message_dict['message_id'], model)
                    )

                # disabled subscriptions during message_new/update to avoid having the system user running the
                # email gateway become a follower of all inbound messages
                nosub_ctx = dict(context, mail_create_nosubscribe=True, mail_create_nolog=True)
######### TO SEND MAIL THROUGH PARTNER-EMAIL ON PARTNER'S REPLY #####                
                if model == 'crm.helpdesk' and message_dict.get('parent_id'):
                    message_obj = Mail_message_pool.browse(cr, uid, message_dict.get('parent_id'))
                    thread_id = thread_id or message_obj.res_id
                    Helpdesk_obj = model_pool.browse(cr, uid, thread_id)
                    if Helpdesk_obj.partner_id.id == message_dict.get('author_id'):
                        context.update({'partner_reply' : 'partner_reply'})
##########################################################
                    
                if thread_id and hasattr(model_pool, 'message_update'):
                    
                    print '\n in if condi message route process',thread_id,model_pool
                    model_pool.message_update(cr, user_id, [thread_id], message_dict, context=nosub_ctx)
                    
###### TO ADD PARTNER NAME IN REPLY TO AND SENT FROM FIELD ON PARTNER'S REPLY ##

#                    Helpdesk_obj = model_pool.browse(cr, uid, thread_id)
#                    vals = {}
#                    print '\n before new changes',Helpdesk_obj,model_pool
#                    if Helpdesk_obj.partner_id.id == message_dict.get('author_id'):
#                        print '\n in if codi of new changes',Helpdesk_obj.email_reply_to,Helpdesk_obj.email_sent_from
                        
#                        if Helpdesk_obj.email_reply_to and Helpdesk_obj.email_reply_to.partition('<')[2].partition('>')[0].strip():
#                            vals.update({'email_reply_to' : Helpdesk_obj.partner_id.name + '<' + Helpdesk_obj.email_reply_to.partition('<')[2].partition('>')[0].strip() + '>'})
                            
#                        elif Helpdesk_obj.email_reply_to:
#                            vals.update({'email_reply_to' : Helpdesk_obj.partner_id.name + '<' + Helpdesk_obj.email_reply_to.strip() + '>'})
                 
                
#                        if Helpdesk_obj.email_sent_from and Helpdesk_obj.email_sent_from.partition('<')[2].partition('>')[0].strip():
#                            vals.update({'email_sent_from' : Helpdesk_obj.partner_id.name + '<' + Helpdesk_obj.email_sent_from.partition('<')[2].partition('>')[0].strip() + '>'})
                            
#                        elif Helpdesk_obj.email_sent_from:
#                            vals.update({'email_sent_from' : Helpdesk_obj.partner_id.name + '<' + Helpdesk_obj.email_sent_from.strip() + '>'})
#                        print '\n sent from and reply to',vals
#                        model_pool.write(cr, uid, thread_id, vals)

##############################################                        
                    
###########TO UPDATE CONVERSATION ON HISTORY/INVITATION MAIL'S REPLY##########
                    
                elif message_dict.get('parent_id') and model == 'crm.helpdesk' and hasattr(model_pool, 'message_update'):
                    print '\n in elif condi of route process \n'
                    message_obj = Mail_message_pool.browse(cr, uid, message_dict.get('parent_id'))
                    new_thread_id = message_obj.res_id
                    model_pool.message_update(cr, user_id, [new_thread_id], message_dict, context=nosub_ctx)
                    thread_id = new_thread_id
################################################################
                else:
                    thread_id = model_pool.message_new(cr, user_id, message_dict, custom_values, context=nosub_ctx)
                    context.update({'update_body':True})
            else:
                if thread_id:
                    raise ValueError("Posting a message without model should be with a null res_id, to create a private message.")
                model_pool = self.pool.get('mail.thread')
            if not hasattr(model_pool, 'message_post'):
                context['thread_model'] = model
                model_pool = self.pool['mail.thread']
            new_msg_id = model_pool.message_post(cr, uid, [thread_id], context=context, subtype='mail.mt_comment', **message_dict)

            if partner_ids:
                # postponed after message_post, because this is an external message and we don't want to create
                # duplicate emails due to notifications
                self.pool.get('mail.message').write(cr, uid, [new_msg_id], {'partner_ids': partner_ids}, context=context)
        return thread_id

        
        
class mail_message(osv.Model):
    _inherit = 'mail.message'        
        
    def create(self, cr, uid, values, context=None):
        context = dict(context or {})
        default_starred = context.pop('default_starred', False)
        if 'email_from' not in values:  # needed to compute reply_to
            values['email_from'] = self._get_default_from(cr, uid, context=context)
        if not values.get('message_id'):
            values['message_id'] = self._get_message_id(cr, uid, values, context=context)
        if 'reply_to' not in values:
            values['reply_to'] = self._get_reply_to(cr, uid, values, context=context)
        if 'record_name' not in values and 'default_record_name' not in context:
            values['record_name'] = self._get_record_name(cr, uid, values, context=context)
################# TO STOP AUTO SEND MAIL ON PARTNER AND HELPDESK RECORD CREATION ######   
        if context.get('update_body') == True:
            newid = super(osv.Model, self).create(cr, uid, values, context)
        else:
            newid = super(osv.Model, self).create(cr, uid, values, context)
            self._notify(cr, uid, newid, context=context,
                         force_send=context.get('mail_notify_force_send', True),
                         user_signature=context.get('mail_notify_user_signature', True))
#################################################################################################
        # TDE FIXME: handle default_starred. Why not setting an inv on starred ?
        # Because starred will call set_message_starred, that looks for notifications.
        # When creating a new mail_message, it will create a notification to a message
        # that does not exist, leading to an error (key not existing). Also this
        # this means unread notifications will be created, yet we can not assure
        # this is what we want.
        if default_starred:
            self.set_message_starred(cr, uid, [newid], True, context=context)
        return newid
        

class project(osv.osv):
    _inherit = "project.project"

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        Task_obj = self.pool.get('project.task')
        project_ids = []
        user_tasks = Task_obj.search(cr, user, [('user_id', '=', user)])
        for task in Task_obj.browse(cr, user, user_tasks):
            if task.project_id.id not in project_ids:
                project_ids.append(task.project_id.id)
        if user != SUPERUSER_ID:
            args += ['|',['user_id','=',user],'|', ['members','in',[user]],'|',['user_id','=',False],['id', 'in', project_ids]]
        return super(project, self).search(cr, user, args, offset=offset, limit=limit, order=order,
            context=context, count=count)
        
        
class task(osv.osv):
    _inherit = "project.task"

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        if user != SUPERUSER_ID:
            args += ['|',['user_id','=',user],['user_id','=',False]]
        return super(task, self).search(cr, user, args, offset=offset, limit=limit, order=order,
            context=context, count=count)


class fetchmail_server(osv.osv):
    """Incoming POP/IMAP mail server account"""
    _inherit = 'fetchmail.server'
    
    _columns = {
            'email_sent_from' : fields.char('Email Sent From', size=128),
            'email_reply_to' : fields.char('Email Replyto', size=128),
    }


class invite_wizard(osv.osv_memory):
    """Inherit add follower metnhod to pass value of send history"""
    _inherit = "mail.wizard.invite"

    _columns = {
        'send_mail': fields.boolean('Send Email',
            help="If checked, the partners will receive an email warning they have been "
                    "added in the document's followers."),
        'history_mail': fields.boolean('The History Email'),
        'invitation_mail': fields.boolean('The Invitation Email'),
    }

    _defaults = {
        'send_mail': False,
    }
    
    def onchange_bool(self, cr, uid, ids, bool_mail, context=None):
        result = {}
        if bool_mail == True:
            result['value'] = {'send_mail' : True}
            return result
    
    def add_followers(self, cr, uid, ids, context=None):
        for wizard in self.browse(cr, uid, ids, context=context):
            model_obj = self.pool[wizard.res_model]
            document = model_obj.browse(cr, uid, wizard.res_id, context=context)

            # filter partner_ids to get the new followers, to avoid sending email to already following partners
            new_follower_ids = [p.id for p in wizard.partner_ids if p not in document.message_follower_ids]
            model_obj.message_subscribe(cr, uid, [wizard.res_id], new_follower_ids, context=context)

            ir_model = self.pool.get('ir.model')
            model_ids = ir_model.search(cr, uid, [('model', '=', model_obj._name)], context=context)
            model_name = ir_model.name_get(cr, uid, model_ids, context=context)[0][1]
            context_new = context
            context_new.update({'history_mail': wizard.history_mail})
            context_new.update({'invitation_mail': wizard.invitation_mail})
#            context_new.update({'add_partner': 'add_partner'})
            # send an email if option checked and if a message exists (do not send void emails)
            if wizard.send_mail and wizard.message and not wizard.message == '<br>':  # when deleting the message, cleditor keeps a <br>
                # add signature
                # FIXME 8.0: use notification_email_send, send a wall message and let mail handle email notification + message box
                signature_company = self.pool.get('mail.notification').get_signature_footer(cr, uid, user_id=uid, res_model=wizard.res_model, res_id=wizard.res_id, context=context)
                wizard.message = tools.append_content_to_html(wizard.message, signature_company, plaintext=False, container_tag='div')

                # send mail to new followers
                # the invite wizard should create a private message not related to any object -> no model, no res_id
                mail_mail = self.pool.get('mail.mail')
                mail_id = mail_mail.create(cr, uid, {
                    'model': wizard.res_model,
                    'res_id': wizard.res_id,
                    'record_name': document.name_get()[0][1],
                    'email_from': self.pool['mail.message']._get_default_from(cr, uid, context=context),
                    'reply_to': self.pool['mail.message']._get_default_from(cr, uid, context=context),
                    'subject': _('Invitation to follow %s: %s') % (model_name, document.name_get()[0][1]),
                    'body_html': '%s' % wizard.message,
                    'auto_delete': False,
                    'message_id': self.pool['mail.message']._get_message_id(cr, uid, {'no_auto_thread': True}, context=context),
                    'recipient_ids': [(4, id) for id in new_follower_ids]
                }, context=context)
                mail_mail.send(cr, uid, [mail_id], context=context_new)
        return {'type': 'ir.actions.act_window_close'}
