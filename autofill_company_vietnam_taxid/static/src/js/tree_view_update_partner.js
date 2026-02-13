odoo.define('autofill_company_vietnam_taxid.treeViewVATUpdate', function (require) {
    "use strict";
    var ListController = require('web.ListController');
    var KanbanController = require('web.KanbanController');

    KanbanController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!this.noLeaf && this.hasButtons && this.$buttons) {
                this.$buttons.on('click', '.o_kanban_button_update_via_vat', this._onClickButtonUpdateViaVat.bind(this)); // add event listener
            }
        },
        _onClickButtonUpdateViaVat: function (ev) {
            // we prevent the event propagation because we don't want this event to
            // trigger a click on the main bus, which would be then caught by the
            // list editable renderer and would unselect the newly created row
            if (ev) {
                ev.stopPropagation();
            }
            var self = this;
            return this._rpc({
                model: 'res.partner',
                method: 'update_partners_from_vat',
                // args: [],
                context: this.initialState.context,
            }).then(function (result) {
                // location.reload();
                self.do_action(result);
            });
        },
    });
    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!this.noLeaf && this.hasButtons) {
                this.$buttons.on('click', '.o_list_button_update_via_vat', this._onClickButtonUpdateViaVat.bind(this)); // add event listener
            }
        },
        _onClickButtonUpdateViaVat: function (ev) {
            // we prevent the event propagation because we don't want this event to
            // trigger a click on the main bus, which would be then caught by the
            // list editable renderer and would unselect the newly created row
            if (ev) {
                ev.stopPropagation();
            }
            var self = this;
            return this._rpc({
                model: 'res.partner',
                method: 'update_partners_from_vat',
                // args: [],
                context: this.initialState.context,
            }).then(function (result) {
                // location.reload();
                self.do_action(result);
            });
        },
    });
});
