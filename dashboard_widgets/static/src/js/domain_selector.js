odoo.define("dashboard_widgets.DomainSelector", function (require) {
    require("web.DomainSelector").include({
        /**
         * MIG: 16.0 - this function hook can probably be removed. This is fixing a standard Odoo issue in
         * addons/web/static/src/legacy/js/widgets/domain_selector.js
         * that was causing the modal body to have overflow set to visible if the domain widget was in the view.
         * This meant that when you edit a dashboard widget the form body would cover the save/discard buttons.
         * Since this is in the legacy directory I am hoping the code is removed in V16
         **/
        on_attach_callback() {
            let $modalBodyEl = this.$el.closest('.modal-body');
            if ($modalBodyEl.length !== 0) {
                $modalBodyEl.css('overflow', 'auto');
            }
        },
    })
});
