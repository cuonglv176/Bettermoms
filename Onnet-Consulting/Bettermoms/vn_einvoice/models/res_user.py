
from odoo import fields, models, api
import requests
from bs4 import BeautifulSoup


class ResUserBranch(models.Model):
    _name = "res.users.branch"

    name = fields.Char('Name')
    branch_id = fields.Many2one('company.branch', string='Company branch')
    user_id = fields.Many2one('res.users', string='User')
    is_update_einvoice = fields.Boolean('Đã tạo trên Einvoice', default=False)


class ResUser(models.Model):
    _inherit = "res.users"

    sellerCode = fields.Char('User Code')

    def is_existed_branch(self, branch_id):
        self.ensure_one()
        user_branch = self.env['res.users.branch'].sudo().search([('user_id', '=', self.id), ('branch_id', '=', branch_id)], limit=1)
        if len(user_branch.ids) > 0:
            return user_branch
        else:
            new = self.env['res.users.branch'].sudo().create({
                            'branch_id': branch_id,
                            'user_id': self.id,
                            'is_update_einvoice': False
                        })
            return new

    def update_to_einvoice(self, branch):
        self.ensure_one()

        sellerCode = self.sellerCode or '11111111'
        sellerName = self.name
        email = self.partner_id.email
        address = 'VietNam'

        userBranch = self.is_existed_branch(branch.id)
        isUpdate = userBranch.is_update_einvoice

        if not isUpdate:
            xmlHeader = """<?xml version="1.0" encoding="utf-8"?>
    <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
        <soap12:Body>
            <UpdateCus xmlns="http://tempuri.org/">
                <XMLCusData>
            """
            xmlContentData = """
                         <![CDATA[
                            <Customers>
                              <Customer>
                                <Name>""" + sellerName + """</Name>
                                <Code>""" + sellerCode + """</Code>
                                <Address>""" + address + """</Address>
                                <Email>""" + email + """</Email>
                                <CusType>0</CusType>
                              </Customer>
                            </Customers>
                         ]]>
            """
            xmlFooter = """
                        </XMLCusData>
                                    <convert>0</convert>
                                    <username>"""+branch.vsi_username+"""</username>
                                    <pass>"""+branch.vsi_password+"""</pass>
                                </UpdateCus>
                            </soap12:Body>
                        </soap12:Envelope>
            """

            headers = {"Content-Type": "text/xml;charset=utf-8"}
            api_url = branch.vsi_domain

            xmlData = xmlHeader + xmlContentData + xmlFooter
            result = requests.post(api_url, data=xmlData.encode('utf-8'), headers=headers)

            soup = BeautifulSoup(result.content.decode("utf-8"), 'xml')
            if soup.find('UpdateCusResult').text == '1':
                if userBranch:
                    userBranch.sudo().update({'is_update_einvoice': True})
        return sellerCode

    # for create user branch test
    def create_seller_branch(self):
        branches = self.env['company.branch'].sudo().search([])
        users = self.env['res.users'].sudo().search([('active', 'in', [True, False])])

        try:
            for user in users:
                for branch in branches:
                    user.is_existed_branch(branch.id)
        except Exception as e:
            Test = True

    def push_to_einvoice(self):
        branches = self.env['company.branch'].sudo().search([])
        users = self.env['res.users'].sudo().search([('active', 'in', [True, False])])

        try:
            for user in users:
                for branch in branches:
                    try:
                        user.update_to_einvoice(branch)
                    except Exception as e:
                        Test = True
        except Exception as e:
            Test = True