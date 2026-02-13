import json
import logging
import re
from odoo import models, fields, api, tools
from jinja2 import Template
import time

logger = logging.getLogger(__name__)


class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    match_text_location_puid = fields.Boolean(
        "PUID", help="Search in statement's PUID to find Invoice/Payment"
    )

    def _get_select_payment_reference_flag(self):
        """
		(
			(move.payment_reference IS NOT NULL OR (payment.id IS NOT NULL AND move.ref IS NOT NULL)) 
			AND 
			(
				regexp_replace(CASE WHEN payment.id IS NULL THEN move.payment_reference ELSE move.ref END, '\s+', '', 'g') = regexp_replace(st_line.payment_ref, '\s+', '', 'g') 
				OR 
				regexp_replace(CASE WHEN payment.id IS NULL THEN move.payment_reference ELSE move.ref END, '\s+', '', 'g') = regexp_replace(st_line_move.narration, '\s+', '', 'g') 
				OR 
				regexp_replace(CASE WHEN payment.id IS NULL THEN move.payment_reference ELSE move.ref END, '\s+', '', 'g') = regexp_replace(st_line_move.ref, '\s+', '', 'g')
			)

            OR

            (move.payment_reference IS NOT NULL OR (payment.id IS NOT NULL AND move.ref IS NOT NULL)) 
            AND
            (
                COALESCE(payment.puid, '') != ''
                AND COALESCE(st_line.puid, '')
                AND (POSITION(payment.puid IN st_line.puid) > 0)
            )
		) AS payment_reference_flag

        --or--

		(
			(move.payment_reference IS NOT NULL OR (payment.id IS NOT NULL AND move.ref IS NOT NULL)) 
			AND 
			(
                COALESCE(payment.puid, '') != ''
                AND COALESCE(st_line.puid, '')
                AND (POSITION(payment.puid IN st_line.puid) > 0)
            )
		) AS payment_reference_flag
        """
        sql = super()._get_select_payment_reference_flag().strip()
        if not self.match_text_location_puid:
            return sql
#         added_query = """
# move.payment_reference IS NOT NULL OR (payment.id IS NOT NULL AND move.ref IS NOT NULL)) 
# AND (COALESCE(payment.puid, '') != '' 
# AND COALESCE(st_line.puid, '') != '' 
# AND (POSITION(payment.puid IN st_line.puid) > 0)
#         """.strip()
        added_query = """
move.payment_reference IS NOT NULL OR (payment.id IS NOT NULL AND move.ref IS NOT NULL)) 
AND (COALESCE(move.name, '') != '' 
AND COALESCE(st_line.puid, '') != '' 
AND (POSITION(LOWER(move.name) IN LOWER(st_line.puid)) > 0)
        """.strip()
        if sql == "FALSE":
            sql = f"""(({added_query}))""".strip()
        else:
            append_sql = f""" OR ({added_query})"""
            sql = sql[:-1] + append_sql + sql[-1]
        return sql
