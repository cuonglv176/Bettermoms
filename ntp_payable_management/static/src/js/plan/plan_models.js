/** @odoo-module */
import KanbanModel from 'web.KanbanModel';

const PlanKanbanModel = KanbanModel.extend({

    async _load(params) {
        this.handle = await this._super(...arguments);
        return this.handle
    }

});

export {
    PlanKanbanModel,
};
