odoo.define('ntp_cne.bill_receipt_suggestion', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var core = require('web.core');
    var field_registry = require('web.field_registry');
    var field_utils = require('web.field_utils');

    var QWeb = core.qweb;
    var _t = core._t;


    var ShowBillReceiptLineWidget = AbstractField.extend({
        events: _.extend({
            'click .bill_receipt_assign': '_onBillReceiptAssign',
            'click .bill_receipt_open': '_onOpenBillReceipt',
        }, AbstractField.prototype.events),
        _render: function () {
            var self = this;
            var info = JSON.parse(this.value);
            if (!info) {
                this.$el.html('');
                return;
            }
            _.each(info.content, function (k, v) {
                k.index = v;
                k.amount_total = field_utils.format.float(k.amount_total, { digits: k.digits });
                if (k.date) {
                    k.date = field_utils.format.date(field_utils.parse.date(k.date, {}, { isUTC: true }));
                }
            });
            this.$el.html(QWeb.render('BillReceiptSuggestion', {
                lines: info.content,
                title: info.title
            }));
        },

        _onBillReceiptAssign: function (event) {
            event.stopPropagation();
            event.preventDefault();
            var self = this;
            var id = $(event.target).data('id') || false;
            this._rpc({
                model: 'tax.invoice',
                method: 'js_assign_bill_receipt',
                args: [JSON.parse(this.value).tax_invoice_id, id],
            }).then(function () {
                self.trigger_up('reload');
            });
        },

        _onOpenBillReceipt: function (event) {
            event.stopPropagation();
            event.preventDefault();
            var moveId = parseInt($(event.target).data('id'));
            var res_model = "account.move";
            var id = moveId;

            //Open form view of account.move with id = move_id
            if (res_model && id) {
                this.do_action({
                    type: 'ir.actions.act_window',
                    res_model: res_model,
                    res_id: id,
                    views: [[false, 'form']],
                    target: 'current'
                });
            }
        },

    })

    // regiter
    field_registry.add('bill_receipt_suggestion', ShowBillReceiptLineWidget);
    return {
        ShowBillReceiptLineWidget: ShowBillReceiptLineWidget
    };

});
