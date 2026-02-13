/** @odoo-module */
import KanbanRenderer from 'web.KanbanRenderer';
import KanbanColumn from 'web.KanbanColumn';
import KanbanRecord from 'web.KanbanRecord';
import view_dialogs from 'web.view_dialogs';
import session from 'web.session';
import core from 'web.core';
import field_utils from 'web.field_utils';

var _t = core._t;

const PlanKanbanColumn = KanbanColumn.extend({
    events: _.extend({
        "click .o_column_download_bulk": '_onColumnDownloadBulk'
    }, KanbanRenderer.prototype.events),

    _onColumnDownloadBulk: function (event) {
        console.log(event)
        event.preventDefault();
        // TODO: make it work
        // var self = this;
        // var record_ids = this.data.data.flatMap(function (x) { return x.res_id })
        // this.do_action("account_payment.action_download_bulk_bank_transfer", {
        //     additionalContext: {
        //         active_ids: record_ids,
        //     },
        // });

        // new view_dialogs.FormViewDialog(this, {
        //     res_model: "ntp.transfer.content.export.wizard",
        //     res_id: 30,
        //     context: session.user_context,
        //     title: _t("Download"),
        //     on_saved: this.trigger_up.bind(this, 'reload'),
        // }).open();
    }
})


const PlanKanbanRenderer = KanbanRenderer.extend({

    config: { // the KanbanRecord and KanbanColumn classes to use (may be overridden)
        KanbanColumn: PlanKanbanColumn,
        KanbanRecord: KanbanRecord,
    },

    async updateState(state, params) {
        var self = this
        if (params?.groupBy == undefined) {
            // copy from BasicRenderer
            this._setState(state);
            if (!params.noRender) {
                await this._render();
            }
            return
        }
        var model = params.groupBy[0] == 'plan_week_id' ? 'account.payment.plan.week' : 'account.payment.plan.month'
        var defs = _.map(state.data, function (record, key) {
            return self._rpc({
                model: model,
                method: 'search_read',
                domain: [['id', '=', record.res_id]],
                fields: ['budget_in', 'budget_out', 'name']
            }).then(function (data) {
                if (_.isEmpty(data) == false) {
                    state.data[key].plan_payment_income = field_utils.format.integer(data[0].budget_in)
                    state.data[key].plan_payment_outcome = field_utils.format.integer(data[0].budget_out)
                }
                console.log("1---record: ", record.res_id)
            })
        })
        console.log("0---")
        await Promise.all(defs).then(function () {
            console.log("1---")
        })
        console.log("2---")

        // copy from BasicRenderer
        this._setState(state);
        if (!params.noRender) {
            await this._render();
        }
    },

    _renderGrouped(fragment) {
        this._super(...arguments);
    },
});

export {
    PlanKanbanRenderer,
};
