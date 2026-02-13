# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# License URL : https://store.webkul.com/license.html/
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################

from odoo import models, fields, api

class Website(models.Model):
    _inherit = "website"

    enable_fb_chat = fields.Boolean(string='Enable Facebook Chat Widget',
        help='Enabling this will enable facebook messenger chat widget in your website.',
        default=False)
    fb_page_id = fields.Char(string='Facebook Page Id',)
    log_in_msg = fields.Text(string='Logged in Greeting Message',
        help="""Default message after user log in to messenger.""",
        default="Hi! How can we help you?", translate=True)
    log_out_msg = fields.Text(string='Logged out Greeting Message',
        help="""Default message after user log out to messenger.""",
        default="Hi! How can we help you?", translate=True)
    fb_messenger_theme_color = fields.Char(string='Messenger Theme color code',
        help="""Provide the theme color hexadecimal for facebook messenger chat box.""",
        default="#0084ff")

class MessengerConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_fb_chat = fields.Boolean(string='Enable Facebook Chat Widget',
        help='Enabling this will enable facebook messenger chat widget in your website.',
        related="website_id.enable_fb_chat", readonly=False)
    fb_page_id = fields.Char(string='Facebook Page Id', required=True,
        related="website_id.fb_page_id", readonly=False)
    log_in_msg = fields.Text(string='Logged in Greeting Message',
        help="""Default message after user log in to messenger.""",
        related="website_id.log_in_msg", readonly=False)
    log_out_msg = fields.Text(string='Logged out Greeting Message',
        help="""Default message after user log out to messenger.""",
        related="website_id.log_out_msg", readonly=False)
    fb_messenger_theme_color = fields.Char(string='Messenger Theme color code',
        help="""Provide the theme color hexadecimal for facebook messenger chat box.""",
        related="website_id.fb_messenger_theme_color", readonly=False)
