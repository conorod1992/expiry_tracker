import "./expiry-tracker-panel-enhanced.js";
import {
  addDays,
  calculateActionDate,
  formatDate,
  relativeFutureDate,
} from "./expiry-tracker-helpers.mjs";
import { actionInfo } from "./expiry-tracker-workflow-helpers.mjs";
import {
  configurationWarnings,
  nextDealableItem,
  selectedItems,
  timelineRows,
} from "./expiry-tracker-dashboard-helpers.mjs";

const Panel = customElements.get("expiry-tracker-panel");

if (Panel && !Panel.prototype.__expiryDashboardEnhanced) {
  const originalRefresh = Panel.prototype.refresh;
  const originalListView = Panel.prototype.listView;
  const originalItemCard = Panel.prototype.itemCard;
  const originalBind = Panel.prototype.bind;
  const originalAction = Panel.prototype.action;
  const originalFormActionability = Panel.prototype.formActionability;
  const originalUpdateFormConditions = Panel.prototype.updateFormConditions;

  Panel.prototype.__expiryDashboardEnhanced = true;

  Panel.prototype.dashboardState = function dashboardState() {
    if (!this._dashboardState) {
      this._dashboardState = { mode: "cards", selected: new Set() };
    }
    return this._dashboardState;
  };

  Panel.prototype.refresh = async function refresh() {
    await originalRefresh.call(this);
    try {
      const result = await this.call("list", { closed: true, limit: 500, sort: "expiry" });
      this.closedItems = result.items || [];
    } catch {
      this.closedItems = [];
    }
    const visibleIds = new Set(this.items.map((item) => item.id));
    const state = this.dashboardState();
    state.selected = new Set([...state.selected].filter((id) => visibleIds.has(id)));
    this.render();
  };

  Panel.prototype.summaryView = function summaryView() {
    const active = this.allItems.filter((item) => item.enabled && !item.closed);
    const attention = active.filter((item) => item.requires_attention);
    const urgent = active.filter((item) => item.status === "urgent");
    const nextExpiry = active
      .filter((item) => item.days_until_expiry >= 0)
      .slice()
      .sort((a, b) => String(a.expiry_date).localeCompare(String(b.expiry_date)))[0] || null;
    const nextAction = nextDealableItem(active);
    const attentionNames = attention.slice(0, 3).map((item) => this.esc(item.name)).join(" · ");
    return `<style>.summary.dashboard-summary{grid-template-columns:minmax(145px,.8fr) 105px minmax(210px,1fr) minmax(210px,1fr)}.summary.dashboard-summary .summary-names{margin-top:4px;line-height:1.35}.dashboard-controls{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 16px;flex-wrap:wrap}.view-switch,.bulk-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.timeline{display:grid;gap:10px;margin:18px 0 28px}.timeline-row{display:grid;grid-template-columns:145px 1fr auto;gap:16px;align-items:center;padding:14px 16px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,12px);cursor:pointer}.timeline-row small,.archive-row small{color:var(--secondary-text-color)}.archive-section{margin-top:32px}.archive-list{display:grid;gap:8px;margin-top:12px}.archive-row{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 14px;border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,12px);background:var(--card-background-color)}.select-box{display:flex;align-items:center;padding-right:4px}.select-box input{width:20px;min-height:20px}.configuration-warning{display:flex;gap:8px;align-items:flex-start;margin-top:12px;padding:10px 12px;border-radius:10px;background:color-mix(in srgb,var(--warning-color,#f9a825) 13%,transparent);color:var(--primary-text-color)}@media(max-width:760px){.summary.dashboard-summary{grid-template-columns:1fr 1fr}.timeline-row{grid-template-columns:1fr}.archive-row{align-items:flex-start;flex-direction:column}}</style><section class="summary dashboard-summary" aria-label="Expiry summary"><div><strong>${attention.length}</strong><span>need attention</span>${attentionNames?`<small class="summary-names">${attentionNames}${attention.length>3?` · +${attention.length-3} more`:""}</small>`:""}</div><div><strong>${urgent.length}</strong><span>urgent</span></div><div class="next"><span>Next thing you can deal with</span><strong>${nextAction?this.esc(nextAction.name):"Nothing queued"}</strong><small>${nextAction?(nextAction.actionable?"Ready now":relativeFutureDate(nextAction.actionable_date)):""}</small></div><div class="next"><span>Next expiry</span><strong>${nextExpiry?this.esc(nextExpiry.name):"Nothing upcoming"}</strong><small>${nextExpiry?formatDate(nextExpiry.expiry_date,this.locale,true):""}</small></div></section>`;
  };

  Panel.prototype.dashboardControls = function dashboardControls() {
    const state = this.dashboardState();
    const selected = selectedItems(this.items, state.selected);
    const admin = this.settings.is_admin;
    return `<section class="dashboard-controls"><div class="view-switch"><button class="button ${state.mode==="cards"?"primary":"secondary"} small" data-action="view-cards"><ha-icon icon="mdi:view-grid-outline"></ha-icon>Cards</button><button class="button ${state.mode==="timeline"?"primary":"secondary"} small" data-action="view-timeline"><ha-icon icon="mdi:timeline-clock-outline"></ha-icon>Timeline</button></div>${admin?`<div class="bulk-actions"><span>${selected.length?`${selected.length} selected`:"Bulk actions"}</span><button class="button secondary small" data-action="select-visible">${selected.length===this.items.length&&this.items.length?"Clear selection":"Select visible"}</button>${selected.length?`<button class="button secondary small" data-action="bulk-enable">Enable</button><button class="button secondary small" data-action="bulk-disable">Disable</button><button class="button secondary small" data-action="bulk-close">Close</button>`:""}</div>`:""}</section>`;
  };

  Panel.prototype.timelineView = function timelineView() {
    const rows = timelineRows(this.items);
    if (!rows.length) return this.emptyFilteredView();
    return `<main class="timeline">${rows.map((item)=>`<article class="timeline-row" tabindex="0" data-open="${item.id}"><div><strong>${formatDate(item.expiry_date,this.locale,true)}</strong><br><small>${item.days_until_expiry<0?"Expired":`${item.days_until_expiry} days remaining`}</small></div><div><strong>${this.esc(item.name)}</strong><br><small>${this.esc(item.category)} · ${actionInfo(item).label}</small></div><span class="status status-${item.status}"><span class="status-dot"></span>${item.status}</span></article>`).join("")}</main>`;
  };

  Panel.prototype.archiveView = function archiveView() {
    const rows = this.closedItems || [];
    if (!rows.length) return "";
    return `<details class="archive-section"><summary><strong>Closed / archive</strong> <span class="count">${rows.length}</span></summary><p class="help">Closed items keep their history but no longer take part in reminders, sensors, calendar or active expiry views.</p><div class="archive-list">${rows.map((item)=>`<div class="archive-row"><div><strong>${this.esc(item.name)}</strong><br><small>Expired ${formatDate(item.expiry_date,this.locale,true)}${item.closed_reason?` · ${this.esc(item.closed_reason)}`:""}</small></div>${this.settings.is_admin?`<button class="button secondary small" data-reopen-id="${item.id}"><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon>Reopen</button>`:""}</div>`).join("")}</div></details>`;
  };

  Panel.prototype.listView = function listView() {
    const state = this.dashboardState();
    if (state.mode === "timeline") {
      return `${this.summaryView()}${this.filtersView()}${this.dashboardControls()}${this.timelineView()}${this.archiveView()}`;
    }
    const base = originalListView.call(this);
    const summaryEnd = base.indexOf("</section>") + 10;
    if (summaryEnd > 9) {
      return `${base.slice(0,summaryEnd)}${this.dashboardControls()}${base.slice(summaryEnd)}${this.archiveView()}`;
    }
    return `${this.dashboardControls()}${base}${this.archiveView()}`;
  };

  Panel.prototype.itemCard = function itemCard(item, quickActions) {
    let html = originalItemCard.call(this, item, quickActions);
    if (!this.settings.is_admin) return html;
    const checked = this.dashboardState().selected.has(item.id) ? "checked" : "";
    html = html.replace(
      '<div class="item-icon">',
      `<label class="select-box" aria-label="Select ${this.esc(item.name)}"><input type="checkbox" data-select-item="${item.id}" ${checked}></label><div class="item-icon">`,
    );
    return html;
  };

  Panel.prototype.formActionability = function formActionability(item) {
    return `${originalFormActionability.call(this,item)}<div id="configuration-warnings" aria-live="polite"></div>`;
  };

  Panel.prototype.updateConfigurationWarnings = function updateConfigurationWarnings() {
    const form = this.shadowRoot.querySelector("#item-form");
    const target = this.shadowRoot.querySelector("#configuration-warnings");
    if (!form || !target) return;
    const data = new FormData(form);
    const expiryDate = data.get("expiry_date");
    const actionableDate = calculateActionDate(
      expiryDate,
      data.get("actionable_mode"),
      data.get("actionable_offset_value"),
      data.get("actionable_offset_unit"),
      data.get("actionable_from"),
    );
    const urgentDays = Number(data.get("urgent_days_before"));
    const urgentDate = expiryDate && Number.isFinite(urgentDays) ? addDays(expiryDate, -urgentDays) : null;
    const warnings = configurationWarnings({ expiryDate, actionableDate: actionableDate === "anytime" ? null : actionableDate, urgentDate });
    target.innerHTML = warnings.map((warning)=>`<div class="configuration-warning"><ha-icon icon="mdi:alert-outline"></ha-icon><span>${this.esc(warning)}</span></div>`).join("");
  };

  Panel.prototype.updateFormConditions = function updateFormConditions() {
    originalUpdateFormConditions.call(this);
    this.updateConfigurationWarnings();
  };

  Panel.prototype.runBulk = async function runBulk(action) {
    const state = this.dashboardState();
    const rows = selectedItems(this.items, state.selected);
    if (!rows.length) return;
    try {
      for (const item of rows) {
        if (action === "close") await this.call("close", { item_id: item.id, reason: "Closed in bulk" });
        else await this.call("update", { item_id: item.id, enabled: action === "enable" });
      }
      state.selected.clear();
      await this.refresh();
      this.showToast(`${rows.length} item${rows.length===1?"":"s"} updated`);
    } catch (error) {
      this.handleError(error);
    }
  };

  Panel.prototype.action = async function action(name) {
    const state = this.dashboardState();
    if (name === "view-cards") { state.mode = "cards"; return this.render(); }
    if (name === "view-timeline") { state.mode = "timeline"; return this.render(); }
    if (name === "select-visible") {
      if (state.selected.size === this.items.length && this.items.length) state.selected.clear();
      else state.selected = new Set(this.items.map((item) => item.id));
      return this.render();
    }
    if (name === "bulk-enable") return this.runBulk("enable");
    if (name === "bulk-disable") return this.runBulk("disable");
    if (name === "bulk-close") return this.runBulk("close");
    return originalAction.call(this, name);
  };

  Panel.prototype.bind = function bind() {
    originalBind.call(this);
    this.shadowRoot.querySelectorAll("[data-select-item]").forEach((element) => {
      element.addEventListener("click", (event) => event.stopPropagation());
      element.addEventListener("change", () => {
        const state = this.dashboardState();
        if (element.checked) state.selected.add(element.dataset.selectItem);
        else state.selected.delete(element.dataset.selectItem);
        this.render();
      });
    });
    this.shadowRoot.querySelectorAll("[data-reopen-id]").forEach((element) => {
      element.addEventListener("click", async () => {
        try {
          await this.call("reopen", { item_id: element.dataset.reopenId });
          await this.refresh();
          this.showToast("Item reopened");
        } catch (error) {
          this.handleError(error);
        }
      });
    });
  };
}
