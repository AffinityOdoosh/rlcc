import {Component, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class ReviewsTable extends Component {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({
            collapse: true,
        });
    }

    _getReviewData() {
        const records = this.props.record.data.review_ids.records;
        return records.map((record) => record.data);
    }

    onToggleCollapse(ev) {
        if (ev) {
            ev.preventDefault();
        }
        this.state.collapse = !this.state.collapse;
    }
}

ReviewsTable.template = "affinity_approval_framework.Collapse";

export const reviewsTableComponent = {
    component: ReviewsTable,
    supportedTypes: ["one2many"],
    relatedFields: [{name: "id", type: "integer"}, {name: "sequence", type: "integer"}, {
        name: "name", type: "char"
    }, {name: "display_status", type: "char"}, {name: "todo_by", type: "char"}, {
        name: "status", type: "char"
    }, {name: "reviewed_formated_date", type: "char"}, {name: "comment", type: "char"}, {
        name: "requested_by", type: "many2one", relation: "partner"
    }, {name: "done_by", type: "many2one", relation: "partner"}],
};

registry.category("fields").add("form.tier_validation", reviewsTableComponent);