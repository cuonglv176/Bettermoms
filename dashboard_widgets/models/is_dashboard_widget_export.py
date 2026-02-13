from odoo import api, fields, models
from odoo.exceptions import UserError
import re, io
import xlsxwriter


class IsDashboardExport(models.Model):
    _inherit = 'is.dashboard'

    def action_export_data(self, widget_id):
        widget = self.env['is.dashboard.widget'].browse(widget_id).exists()
        if widget:
            if widget.display_mode not in ('card', 'graph', 'record_list', 'table'):
                raise UserError("Downloading dashboard item of type {} is not currently supported".format(widget.display_mode))
            return {
                'type': 'ir.actions.act_url',
                'url': '/dashboard/download_export_data/{}/{}'.format(self.id, widget_id),
            }

    def action_export_all_data(self):
        widget_ids = self.widget_ids.filtered(lambda a: a.display_mode in ['card', 'graph', 'record_list', 'table'])
        if not widget_ids:
            raise UserError("There are no dashboard items to download")

        return {
            'type': 'ir.actions.act_url',
            'url': '/dashboard/download_export_all_data/{}'.format(self.id),
        }

    def export_dashboard_data(self, worksheet, workbook, starting_row, widget):
        render_data = widget.get_render_data()
        heading_format = workbook.add_format({'bold': True, 'font_color': 'green'})

        row = starting_row
        worksheet.write_row(row, 0, [widget.name], heading_format)

        row += 1
        if widget.display_mode == 'card':
            primary_value = widget.query_1_config_measure_field_id.field_description if widget.card_primary_display == 'measure_value' else 'Value'

            worksheet.write_row(row, 0, [primary_value, render_data['count_display']]); row += 1
            if widget.widget_type == 'count_over_total':
                worksheet.write_row(row, 0, [widget.query_2_config_measure_field_id.field_description or 'Value 2',render_data['total_display']]); row += 1
            if widget['has_forecast_1'] and widget['show_expected_1']:
                worksheet.write_row(row, 0,[render_data['show_expected_1_label'], render_data['expected_count_display']]); row += 1
            if widget['query_1_config_enable_goal'] and widget['show_goal_1']:
                worksheet.write_row(row, 0,[render_data['show_goal_1_label'], render_data['current_goal_count_display']]); row += 1
            if widget['query_1_config_enable_goal'] and widget['show_variation_1']:
                worksheet.write_row(row, 0, [render_data['show_variation_1_label'],render_data['goal_count_variance_display']]); row += 1
            if widget['has_forecast_1'] and widget['show_forecast_1']:
                worksheet.write_row(row, 0,[render_data['show_forecast_1_label'], render_data['forecast_count_display']]); row += 1
            if widget['has_forecast_1'] and widget['query_1_config_enable_goal'] and widget['show_forecast_1'] and widget['show_forecasted_variation_1']:
                worksheet.write_row(row, 0, [render_data['show_forecasted_variation_1_label'],render_data['goal_forecast_count_variance_display']]); row += 1
            if widget['has_forecast_2'] and widget['show_expected_2']:
                worksheet.write_row(row, 0,[render_data['show_expected_2_label'], render_data['expected_total_display']]); row += 1
            if widget['query_2_config_enable_goal'] and widget['show_goal_2']:
                worksheet.write_row(row, 0,[render_data['show_goal_2_label'], render_data['current_goal_total_display']]); row += 1
            if widget['query_2_config_enable_goal'] and widget['show_variation_2']:
                worksheet.write_row(row, 0, [render_data['show_variation_2_label'],render_data['goal_total_variance_display']]); row += 1
            if widget['has_forecast_2'] and widget['show_forecast_2']:
                worksheet.write_row(row, 0,[render_data['show_forecast_2_label'], render_data['forecast_total_display']]); row += 1
            if widget['has_forecast_2'] and widget['query_2_config_enable_goal'] and widget['show_forecast_2'] and widget['show_forecasted_variation_2']:
                worksheet.write_row(row, 0, [render_data['show_forecasted_variation_2_label'],render_data['goal_forecast_total_variance_display']]);row += 1

        elif widget.display_mode == 'graph':
            chart_data = widget.get_dashboard_data()
            if not chart_data:
                worksheet.write_row(row, 0, ["No data"])
                row += 1
            else:
                worksheet.write_row(row, 1, ["{}".format(l) for l in chart_data['data']['labels']]); row += 1
                for i, ds in enumerate(chart_data['data']['datasets']):
                    ds_label = "{}".format(ds['label']) if len(chart_data['data']['datasets']) > 1 else ""
                    worksheet.write_row(row, 0, [ds_label] + ds['data'])
                    row += 1

        elif widget.display_mode in ('record_list', 'table'):
            worksheet.write_row(row, 0, ["{}".format(l['name']) for l in render_data['table']['headers']]); row += 1
            for i, row_data in enumerate(render_data['table']['rows']):
                worksheet.write_row(row, 0, ["{}".format(l['value']) for l in row_data])
                row += 1
        else:
            raise UserError("Downloading dashboard type {} is not currently supported".format(widget.display_mode))

        return row + 2

    def action_export_widget_data_get_download_file(self, dashboard, widgets=[]):
        today = fields.Date.context_today(widgets[0])
        filename = "{}_{}_{}.xlsx".format(re.sub(r'[^\w\d-]', '_', dashboard.name),re.sub(r'[^\w\d-]', '_', widgets[0].name) if len(widgets) == 1 else 'All', today.strftime('%Y-%m-%d'))
        buffer_xlsx = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer_xlsx)
        worksheet = workbook.add_worksheet()

        bold = workbook.add_format({'bold': True})
        worksheet.write_row(0, 0, [dashboard.name], bold);
        starting_row = 2
        for widget in widgets:
            starting_row = dashboard.export_dashboard_data(worksheet, workbook, starting_row, widget) + 1

        workbook.close()
        buffer_xlsx.seek(0)
        xls_bytes = buffer_xlsx.read()

        return xls_bytes, filename
