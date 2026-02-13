odoo.define('ntp_payable_management.tree_view_button_plan_create', function (require) {
    "use strict";
    var ListController = require('web.ListController');

    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!this.noLeaf && this.hasButtons) {
                this.$buttons.on('click', '.o_list_button_plan_create', this._onClickButtonPlanCreate.bind(this)); // add event listener
                // this.$buttons.on('click', '.o_list_button_auto_match_vendor', this._onClickButtonAutoMatchInvoice.bind(this)); // add event listener
            }
        },
        _onClickButtonPlanCreate: function (ev) {
            // we prevent the event propagation because we don't want this event to
            // trigger a click on the main bus, which would be then caught by the
            // list editable renderer and would unselect the newly created row
            if (ev) {
                ev.stopPropagation();
            }
            var self = this;
            return this._rpc({
                model: 'account.payment.plan.week',
                method: 'plan_create',
                args: [],
                context: this.initialState.context,
            }).then(function (result) {
                // location.reload();
                self.do_action(result);
            });
        },

    });
});
