odoo.define('ntp_sale_overdue.overdue_payment', function (require) {
    "use strict";

    var core = require('web.core');
    var session = require('web.session');
    var fieldRegistry = require('web.field_registry');
    var AbstractField = require('web.AbstractField');
    var fieldUtils = require('web.field_utils');
    var QWeb = core.qweb;
    Number.prototype.format = function(n, x) {
        var re = '\\d(?=(\\d{' + (x || 3) + '})+' + (n > 0 ? '\\.' : '$') + ')';
        return this.toFixed(Math.max(0, ~~n)).replace(new RegExp(re, 'g'), '$&,');
    };
    var OverDuePayment = AbstractField.extend({
        template: 'OverDue_Template',
        supportedFieldTypes: ['char'],
        model_id: null,
        html: null,
        start: function() {
            this._super.apply(this, arguments);
            this.render_value()
        },

        render_value: function () {
            var self = this;
            var options = {
                value: this._formatValue(this.value || 0),
            };
            if (! this.attrs.nolabel) {
                if (this.nodeOptions.label_field && this.recordData[this.nodeOptions.label_field]) {
                    options.text = this.recordData[this.nodeOptions.label_field];
                } else {
                    options.text = this.string;
                }
            }
            this.$el.html(QWeb.render("OverDue_Template", options));
            this._rpc({
            model: this.model,
            method: 'get_overdue_payment_info',
            args: [[this.res_id]],
            }).then(function (result) {
                var options = {}
                var html = ''

                function get_state(state) {
                    if (state == 'not_paid'){
                        return 'Not Paid'
                    }
                    else if (state == 'partial'){
                        return 'Partial'
                    }
                    else{
                        return 'Paid'
                    }
                }
                if(result){
                    html += '<table class="oe_list_content">\
                                <tr class="item_header">\
                                    <th class="n-digit">Payment Date</th>\
                                    <th class="digit">Due Date</th>\
                                    <th class="digit">No of Late Payments</th>\
                                    <th class="digit">Overdue Amount</th>\
                                    <th class="digit">Amount Due</th>\
                                </tr>'
                    var outstanding_amount = 0
                    outstanding_amount += parseInt(result.overdue_amount)
                    html += '<tr class="item_data">'
                    html += '<td class="n-digit">'+result.payment_date+'</td>'
                    html += '<td class="digit">'+result.due_date+'</td>'
                    html += '<td class="digit">'+result.no_late_payment+'</td>'
                    html += '<td class="digit">'+result.overdue_amount.format() +'</td>'
                    html += '<td class="digit">'+result.amount_due.format() +'</td>'
                    html += '</tr>'
                    // html += '<tr class="item_data foot">' +
                    //     '<td class="n-digit">Sum</td>' +
                    //     '<td class="digit" colspan="3">'+outstanding_amount.format()+'</td>' +
                    //     '</tr>'
                    html += '</table>'
                }
                self.html = html;
            });
        },

        /**
         * OverDuePayment widgets are always set since they basically only display info.
         *
         * @override
         */
        isSet: function () {
            return true;
        },
        renderElement: function () {
            this._super();
            var self = this;

            this.$el.hover(function(){
                var options = {}
                var h = $(window).outerHeight();
                    var w = $(window).outerWidth();
                options['html'] = ''
                $(QWeb.render('ViewOverDue', options)).insertAfter('body');
                var view = $('#view_over_due')
                view.html(self.html);
                view.css({'top': h/2-view.outerHeight()/2 +'px', 'left': w/2-view.outerWidth()/2 + 'px'})
            }, function(){
                $('#view_over_due').remove();
            });
    },
    })
    fieldRegistry.add('overdue_payment', OverDuePayment)
})