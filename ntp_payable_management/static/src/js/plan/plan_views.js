/** @odoo-module */
import { PlanKanbanController } from './plan_controllers';
import { PlanKanbanModel } from './plan_models';
import { PlanKanbanRenderer } from './plan_renderers';
import KanbanView from 'web.KanbanView';
import viewRegistry from 'web.view_registry';

const PlanKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Renderer: PlanKanbanRenderer,
        Model: PlanKanbanModel,
        Controller: PlanKanbanController,
    }),

});
viewRegistry.add('plan_kanban', PlanKanbanView);

export {
    PlanKanbanView
};
