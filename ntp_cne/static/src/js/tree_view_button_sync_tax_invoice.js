odoo.define('ntp_cne.tree_view_button_sync_tax_invoice', function (require) {
    "use strict";
    var ListController = require('web.ListController');

    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!this.noLeaf && this.hasButtons) {
                this.$buttons.on('click', '.o_list_button_sync_tax_invoice', this._onClickButtonSyncTaxInvoice.bind(this)); // add event listener
                // this.$buttons.on('click', '.o_list_button_auto_match_vendor', this._onClickButtonAutoMatchInvoice.bind(this)); // add event listener
            }
        },
        _onClickButtonSyncTaxInvoice: function (ev) {
            // we prevent the event propagation because we don't want this event to
            // trigger a click on the main bus, which would be then caught by the
            // list editable renderer and would unselect the newly created row
            if (ev) {
                ev.stopPropagation();
            }
            var self = this;
            return this._rpc({
                model: 'tax.invoice',
                method: 'sync_tax_invoice',
                args: [],
                context: this.initialState.context,
            }).then(function (result) {
                // location.reload();
                self.do_action(result);
            });
        },

        // _onClickButtonAutoMatchInvoice: function(ev) {
        //     // we prevent the event propagation because we don't want this event to
        //     // trigger a click on the main bus, which would be then caught by the
        //     // list editable renderer and would unselect the newly created row
        //     if (ev) {
        //         ev.stopPropagation();
        //     }
        //     var self = this;
        //     return this._rpc({
        //         model: 'tax.invoice',
        //         method: 'auto_match_vendor',
        //         args: [self.getSelectedIds()],
        //         context: this.initialState.context,
        //     }).then(function (result) {
        //         // location.reload();
        //         self.do_action(result);
        //     });
        // }
    });
});
