import "./expiry-tracker-panel.js";
import { groupItems, isPassiveItem, recurrenceLabel } from "./expiry-tracker-helpers.mjs";
import { ACTION_TYPES, actionInfo, matchingAlias } from "./expiry-tracker-workflow-helpers.mjs";

const Panel = customElements.get("expiry-tracker-panel");

if (Panel && !Panel.prototype.__expiryWorkflowEnhanced) {
  const originalListView = Panel.prototype.listView;
  const originalItemCard = Panel.prototype.itemCard;
  const originalAcknowledgedSection = Panel.prototype.acknowledgedSection;
  const originalDetailView = Panel.prototype.detailView;
  const originalModalView = Panel.prototype.modalView;
  const originalOpenRenew = Panel.prototype.openRenew;
  const originalAction = Panel.prototype.action;
  const originalUpdateFormConditions = Panel.prototype.updateFormConditions;
  const originalFormAdvanced = Panel.prototype.formAdvanced;
  const originalHistoryView = Panel.prototype.historyView;

  Panel.prototype.__expiryWorkflowEnhanced = true;

  Panel.prototype.listView = function listView() {
    const groups = groupItems(this.items);
    if (!groups.informational.length) return originalListView.call(this);
    if (!this.items.length && !this.hasFilters()) {
      return `${this.summaryView()}${this.filtersView()}${this.firstUseView()}`;
    }
    return `${this.summaryView()}${this.filtersView()}<main class="groups">${
      this.hasFilters() && !this.items.length
        ? this.emptyFilteredView()
        : `${this.attentionSection(groups.attention)}${this.acknowledgedSection(groups.acknowledged)}${this.itemSection(
            "Expired — no action needed",
            "These items are tracked for reference only. Their expiry does not create work or a reminder to dismiss.",
            groups.informational,
          )}${this.itemSection(
            "Coming up",
            "Items worth keeping an eye on, but which do not need action yet.",
            groups.comingUp,
          )}${this.laterSection(groups.later)}`
    }</main>`;
  };

  Panel.prototype.formRenewal = function formRenewal(item) {
    const selected = item.action_type || "renew";
    const actionOptions = ACTION_TYPES.map(
      ([value, label]) =>
        `<option value="${value}" ${selected === value ? "selected" : ""}>${label}</option>`,
    ).join("");
    return this.section(
      4,
      "Action & repeat",
      `<div class="form-grid"><label><span>What do you need to do?</span><select name="action_type">${actionOptions}</select></label><label class="custom-action-label" ${selected === "custom" ? "" : "hidden"}><span>Completed wording</span><input name="custom_action_label" maxlength="80" value="${this.esc(item.custom_action_label || "")}" placeholder="For example, serviced"><small>Used after “Mark as …” on the item.</small></label><label><span>Typical repeat period</span><select name="recurrence_months"><option value="">I’ll enter the new date myself</option>${[[12,"1 year"],[36,"3 years"],[60,"5 years"],[120,"10 years"]].map(([value,label])=>`<option value="${value}" ${item.recurrence_months==value?"selected":""}>${label}</option>`).join("")}</select></label></div><p class="help renewal-help"><ha-icon icon="mdi:information-outline"></ha-icon>For renew, replace, review, re-test, re-register, check and custom actions, completing the task records the next expiry date. “Cancel / end” closes the item instead.</p>`,
    );
  };

  Panel.prototype.formAdvanced = function formAdvanced(item) {
    return originalFormAdvanced.call(this, item).replace(
      '<span>Other names <small>comma separated</small></span><input name="aliases" value="',
      '<span>Search names / aliases <small>comma separated</small></span><input name="aliases" aria-describedby="alias-help" value="',
    ).replace(
      'placeholder="For search and Assist"></label>',
      'placeholder="For example, passport, licence"><small id="alias-help">These names are searchable and help Assist find this item even when you do not use its exact title.</small></label>',
    );
  };

  Panel.prototype.updateFormConditions = function updateFormConditions() {
    originalUpdateFormConditions.call(this);
    const form = this.shadowRoot.querySelector("#item-form");
    if (!form) return;
    const custom = form.elements.action_type?.value === "custom";
    const field = form.querySelector(".custom-action-label");
    if (!field) return;
    field.hidden = !custom;
    const input = form.elements.custom_action_label;
    input.required = custom;
    if (!custom) input.setCustomValidity("");
  };

  Panel.prototype.itemCard = function itemCard(item, quickActions) {
    const passive = isPassiveItem(item);
    const displayItem = passive
      ? {
          ...item,
          acknowledged: false,
          actionable: false,
          actionable_date: null,
          attention_stage: null,
          requires_attention: false,
        }
      : item;
    const info = actionInfo(item);
    let html = originalItemCard.call(this, displayItem, quickActions && !passive).replace(
      "Mark as renewed",
      this.esc(info.button),
    );
    if (passive) {
      html = html.replace(
        '<div class="next-action"></div>',
        '<div class="next-action">Tracked for reference — no action required</div>',
      );
    }
    const alias = matchingAlias(item, this.filters?.search);
    if (alias) {
      const marker = '</div></div><div class="item-side">';
      html = html.replace(
        marker,
        `</div><div class="item-meta"><ha-icon icon="mdi:tag-outline"></ha-icon>Matched alias: ${this.esc(alias)}</div></div><div class="item-side">`,
      );
    }
    return html;
  };

  Panel.prototype.acknowledgedSection = function acknowledgedSection(items) {
    return originalAcknowledgedSection
      .call(this, items)
      .replace("have not been marked as renewed", "have not been completed yet");
  };

  Panel.prototype.historyView = function historyView(history) {
    return originalHistoryView.call(this, history).replaceAll("Marked as renewed", "Completion recorded");
  };

  Panel.prototype.detailView = function detailView(item) {
    if (!item) return originalDetailView.call(this, item);
    const info = actionInfo(item);
    let html = originalDetailView
      .call(this, item)
      .replaceAll("Mark as renewed", this.esc(info.button))
      .replace("record the new expiry date here", "record completion here")
      .replace("Renewal settings", "Action settings")
      .replace("Typical renewal period", "Typical repeat period")
      .replace("How renewal works", "How completion works")
      .replace(
        "You’ll confirm the renewed item’s new expiry date. It is never changed automatically.",
        info.value === "cancel"
          ? "Completing this action closes the item without deleting its history."
          : "You’ll confirm the next expiry date after completing the real-world task. It is never changed automatically.",
      );
    if (isPassiveItem(item)) {
      const title = item.days_until_expiry < 0 ? "Expired — no action needed" : "Informational tracking only";
      html = html.replace(
        /<section class="what-next">[\s\S]*?<\/section>/,
        `<section class="what-next"><div><h3>${title}</h3><p>This item is tracked for its expiry date, but Expiry Tracker will not treat it as work you need to complete or a reminder you need to dismiss.</p></div></section>`,
      );
      html = html.replace(
        /<section class="info-card"><h3>Dates<\/h3>[\s\S]*?<\/section>/,
        `<section class="info-card"><h3>Dates</h3>${this.dateRow("Expires", item.expiry_date, "calendar-remove")}${this.dateRow("Reminders begin", item.warning_date, "bell-outline")}</section>`,
      );
      html = html.replace(
        /<dt>Current stage<\/dt><dd>[\s\S]*?<\/dd>/,
        "<dt>Tracking mode</dt><dd>Informational only · no dismissal needed</dd>",
      );
      html = html.replace(
        /<dt>Repeats<\/dt><dd>[\s\S]*?<\/dd>/,
        "<dt>Repeats</dt><dd>No repeated attention reminders</dd>",
      );
      html = html.replace(
        /<section class="info-card"><h3>Action settings<\/h3>[\s\S]*?<\/section>/,
        `<section class="info-card"><h3>Tracking settings</h3><dl><dt>Mode</dt><dd>Informational only</dd><dt>Typical repeat period</dt><dd>${this.esc(recurrenceLabel(item.recurrence_months))}</dd><dt>Date updates</dt><dd>Edit the item when the tracked expiry changes.</dd></dl></section>`,
      );
    }
    if (item.aliases?.length) {
      html = html.replace(
        '<div class="detail-grid">',
        `<div class="detail-grid"><section class="info-card"><h3>Search names</h3><p class="help">${item.aliases.map((alias)=>this.esc(alias)).join(" · ")}</p></section>`,
      );
    }
    if (this.settings.is_admin) {
      html = html.replace(
        '<button class="button danger" data-action="delete">',
        '<button class="button secondary" data-action="duplicate"><ha-icon icon="mdi:content-copy"></ha-icon>Duplicate</button><button class="button danger" data-action="delete">',
      );
    }
    return html;
  };

  Panel.prototype.openRenew = function openRenew(item = this.selected) {
    if (item?.action_type === "cancel") {
      this.modal = { type: "complete-cancel", item };
      this.render();
      return;
    }
    return originalOpenRenew.call(this, item);
  };

  Panel.prototype.modalView = function modalView() {
    if (this.modal?.type === "complete-cancel") {
      const item = this.modal.item;
      return `<div class="dialog-backdrop" data-backdrop><div class="dialog" role="dialog" aria-modal="true" aria-labelledby="complete-cancel-title" tabindex="-1" data-dialog><div class="dialog-icon success-icon"><ha-icon icon="mdi:check-circle-outline"></ha-icon></div><h2 id="complete-cancel-title">Mark ${this.esc(item.name)} as cancelled?</h2><p>This records the action as complete and closes the item. Its history is retained; it is not deleted.</p><div class="dialog-actions"><button class="button secondary" data-action="close-modal">Cancel</button><button class="button primary" data-action="confirm-cancel-completion">Mark as cancelled</button></div></div></div>`;
    }
    const item = this.modal?.item;
    const info = actionInfo(item || {});
    return originalModalView
      .call(this)
      .replaceAll("Mark as renewed", this.esc(info.button))
      .replace(
        "real-world renewal or replacement",
        `real-world ${this.esc(info.label.toLowerCase())} action`,
      )
      .replace("expiry date of the renewed item", "next expiry date after completing the task");
  };

  Panel.prototype.submitRenewal = async function submitRenewal(event) {
    event.preventDefault();
    const item = this.modal.item;
    const info = actionInfo(item);
    const newDate = new FormData(event.target).get("new_expiry_date");
    try {
      this.selected = await this.call("renew", { item_id: item.id, new_expiry_date: newDate });
      this.modal = null;
      this.view = "detail";
      this.showToast(`${this.selected.name} marked as ${info.completed}`);
    } catch (error) {
      this.handleError(error);
    }
  };

  Panel.prototype.duplicateItem = async function duplicateItem() {
    const item = this.selected;
    if (!item) return;
    const keys = [
      "expiry_date",
      "aliases",
      "category",
      "notes",
      "enabled",
      "important",
      "expose_entity",
      "requires_action",
      "action_type",
      "custom_action_label",
      "actionable_mode",
      "actionable_offset_value",
      "actionable_offset_unit",
      "actionable_from",
      "warning_thresholds",
      "urgent_days_before",
      "notify_actionable",
      "notify_urgent",
      "notify_expiry",
      "require_acknowledgement",
      "repeat_until_acknowledged",
      "repeat_interval_hours",
      "recurrence_months",
    ];
    const payload = { name: `${item.name} copy` };
    for (const key of keys) payload[key] = item[key];
    try {
      this.selected = await this.call("create", payload);
      this.view = "detail";
      this.showToast("Duplicate created");
    } catch (error) {
      this.handleError(error);
    }
  };

  Panel.prototype.completeCancellation = async function completeCancellation() {
    const item = this.modal.item;
    try {
      await this.call("close", { item_id: item.id, reason: "Marked as cancelled" });
      this.modal = null;
      this.selected = null;
      this.view = "list";
      await this.refresh();
      this.showToast(`${item.name} marked as cancelled and closed`);
    } catch (error) {
      this.handleError(error);
    }
  };

  Panel.prototype.action = async function action(name) {
    if (name === "duplicate") return this.duplicateItem();
    if (name === "confirm-cancel-completion") return this.completeCancellation();
    return originalAction.call(this, name);
  };
}
