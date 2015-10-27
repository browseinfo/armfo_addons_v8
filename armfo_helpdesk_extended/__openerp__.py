# -*- coding: utf-8 -*-
##############################################################################
#
#    This module uses OpenERP, Open Source Management Solution Framework.
#    Copyright (C) 2015-Today BrowseInfo (<http://www.browseinfo.in>)
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
{
    "name" : "CRM Helpdesk",
    "version" : "1.0",
    "depends" : ['crm_helpdesk', 'sale', 'project_issue', 'crm', 'account', 'crm_claim', 'project', 'calendar', 'mail', 'base', 'base_setup', 'sales_team', 'stock', 'web'],
    "description": """
        This module is used to add short links with different options in crm helpdesk. [for Armfo system]
    """,
    "author": 'BrowseInfo',
    "website" : "www.browseinfo.in",
    "data" : [
        'security/helpdesk_security.xml',
        'security/ir.model.access.csv',
        'crm_helpdesk_view.xml',
        'email_template_view.xml',
        'helpdesk_action_rule.xml',
    ],
    'qweb' : [
        "static/src/xml/*.xml",
    ],
    
    "auto_install": False,
    "installable": True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
