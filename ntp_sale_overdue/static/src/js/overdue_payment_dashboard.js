odoo.define('ntp_sale_overdue.overdue_payment_dashboard', function (require) {
    "use strict";

    var core = require('web.core');
    var session = require('web.session');
    var fieldRegistry = require('web.field_registry');
    var AbstractField = require('web.AbstractField');
    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');
    var ListRenderer = require('web.ListRenderer');

    var QWeb = core.qweb;

    const SaleOverDueDashboardMixin = {
        _render: async function () {
            var self = this;
            await this._super(...arguments);
            const result = renderDashboardOverdue(self, self.state.domain).then(result => {
                self.$el.parent().find('.o_overdue_sale_container').remove();
                const elem = QWeb.render('ntp_sale_overdue.dashboard_list_header', {
                    overdue_data: result,
                    render_monetary_field: self.render_monetary_field,
                });
                self.$el.before(elem);
            });


        },
        render_monetary_field: function (value, currency_id) {
            value = value.toFixed(2);
            var currency = session.get_currency(currency_id);
            if (currency) {
                if (currency.position === "after") {
                    value += currency.symbol;
                } else {
                    value = currency.symbol + value;
                }
            }
            return value;
        }
};
    const renderDashboardOverdue = async (self, domain) =>{
        const result = await self._rpc({
                model: 'sale.order',
                method: 'get_overdue_dashboard',
                args: [domain],
                context: self.state ? self.state.context : {},
            });
        return result
    }

    // Expense List Renderer
    var SaleListViewDashboardHeader = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Renderer: ListRenderer.extend(SaleOverDueDashboardMixin),
        })
    });
    viewRegistry.add('sale_tree_dashboard_header', SaleListViewDashboardHeader);


    ListController.include({
         _updateControlPanel() {
            this._super(...arguments);
            var self = this;
            if ($('.o_overdue_sale_container').length > 0) {
                var domain = [];
                domain.push(...self.initialState.domain)
                var ids = this.getSelectedIds();
                if (ids.length > 0){
                    domain.push(...[['id', 'in', ids]])
                }
                 const result = renderDashboardOverdue(self, domain).then(result => {
                  $('.o_overdue_sale_container').remove();
                    const elem = QWeb.render('ntp_sale_overdue.dashboard_list_header', {
                        overdue_data: result,
                        render_monetary_field: self.render_monetary_field,
                    });
                    $('.o_list_optional_columns').before(elem);
                 }

                )
            }


        },
    })

})