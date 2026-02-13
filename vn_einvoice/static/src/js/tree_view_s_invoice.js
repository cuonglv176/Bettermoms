odoo.define('vn_einvoice.treeViewSInvoice', function (require) {
    "use strict";
    var ListController = require('web.ListController');

    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!this.noLeaf && this.hasButtons) {
                this.$buttons.on('click', '.o_list_button_sync_s_invoice', this._onClickButtonSyncSInvoice.bind(this)); // add event listener
            }
        },
        _onClickButtonSyncSInvoice: function (ev) {
            // we prevent the event propagation because we don't want this event to
            // trigger a click on the main bus, which would be then caught by the
            // list editable renderer and would unselect the newly created row
            if (ev) {
                ev.stopPropagation();
            }
            var self = this;
            return this._rpc({
                model: 'invoice.viettel',
                method: 'sync_s_invoice',
                args: [],
                context: this.initialState.context,
            }).then(function (result) {
                // location.reload();
                self.do_action(result);
            });
        },
    });
});
