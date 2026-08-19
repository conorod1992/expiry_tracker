# Expiry Tracker

Expiry Tracker is a local-first Home Assistant custom integration for passports, driving licences, insurance policies, medical cards, professional registrations, pet licences, certificates, warranties, domains, subscriptions, and other administrative deadlines.

Its central question is not merely **“what expires soon?”** but **“what actually needs my attention now?”** An approaching expiry does not require action until its configured actionable window begins.

## Highlights

- Polished, responsive, build-free sidebar with search, filters, sorting, detail views, guided forms, renewal, acknowledgement, history, and accessible keyboard navigation
- Stable immutable UUIDs; renaming never creates a new entity
- Explicit warning, actionable, urgent, and expiry dates
- Aggregate sensors, optional per-item sensors, and an expiry calendar
- Structured mutation and response-data query actions
- Read-only Assist/LLM tool designed to favour items that genuinely need attention
- Versioned, bounded, concurrency-safe local storage; no account, cloud, telemetry, or external network access
- Notification transition deduplication and optional repeat-until-acknowledged escalation through a normal Home Assistant notification service

## Installation and setup

### HACS

1. In HACS, add `https://github.com/conorod1992/expiry_tracker` as a custom integration repository.
2. Install **Expiry Tracker** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**, search for **Expiry Tracker**, and add it.
4. Open **Expiry Tracker** in the sidebar and add items.

### Manual

Copy `custom_components/expiry_tracker` into your Home Assistant `config/custom_components` directory, restart, and add the integration from Devices & services.

The integration creates one collection-level config entry. Individual records are deliberately managed in the dedicated sidebar or through structured actions—not as dozens of helpers/config entries.

## Status model

Every enabled item has exactly one derived status. Precedence is:

1. `expired` — today is after the expiry date
2. `urgent` — the urgent window has begun, including the expiry day
3. `actionable` — action can now be taken
4. `warning` — advance notice has begun, but the item is not yet actionable
5. `valid` — none of the above

These meanings are intentionally separate:

| Concept | Meaning |
|---|---|
| Expiry date | The last date the item remains valid. It becomes `expired` the following day. |
| Warning | Advance awareness. A warning alone does **not** mean action is possible. Multiple thresholds such as 180, 90, 30, 7, and 1 days are supported. |
| Actionable | The date on which the user can actually begin renewal or another task. Configure it as immediate, a day/month offset, or a specific date. |
| Urgent | A higher-priority window near expiry. Urgent takes precedence over actionable. |

`requires_attention` is true only when an enabled item is actionable (including urgent/expired) and has not been acknowledged. Acknowledgement quiets attention/escalation without pretending renewal happened. It never changes the expiry date or status.

Calendar-month offsets clamp safely at month ends. For example, one month before 31 March is 28 February (29 in a leap year).

## Sidebar

The main view provides compact cards rather than an admin table. It shows category, expiry date, human time remaining, status, actionability, importance, and enabled state. Summary tiles show attention, urgent and expired counts plus the next expiry.

Available controls include:

- search across names, aliases, and categories
- category, status, enabled/disabled, actionable-only, and important-only filters
- sorting by next expiry, name, urgency, or actionable date
- loading, error, filtered-empty, and first-run empty states

The add/edit form uses date inputs, toggles, category suggestions, warning thresholds, progressive acknowledgement/escalation controls, and clear actionability choices. The detail view shows the calculated timeline, reminder policy, acknowledgement state, recurrence, bounded history, and all workflows.

Renew is emphasized when appropriate. It always records the previous expiry and resets acknowledgement and notification state. Without configured recurrence, a new date is required. With recurrence, the user must still explicitly select **Renew**—dates never advance silently.

## Entities

- `sensor.next_expiry` — date and bounded metadata for the next enabled expiry
- `sensor.next_actionable_expiry` — next unacknowledged actionable expiry
- `sensor.expiry_tracker_actionable` — count requiring attention now
- `sensor.expiry_tracker_urgent` — urgent count
- `sensor.expiry_tracker_expired` — expired count
- `calendar.expiry_tracker` — enabled expiry dates

When **Expose individual sensor** is enabled, the stable item UUID backs a date sensor whose bounded attributes include expiry, days remaining, status, actionable state/date, urgent date, acknowledgement, category, and importance.

## Actions

Mutations use stable `item_id` values:

- `expiry_tracker.create_item`
- `expiry_tracker.update_item`
- `expiry_tracker.delete_item`
- `expiry_tracker.renew_item`
- `expiry_tracker.acknowledge_item`
- `expiry_tracker.reset_acknowledgement`

Queries return structured response data for automations and conversation agents:

- `expiry_tracker.search_items`
- `expiry_tracker.get_upcoming`
- `expiry_tracker.get_actionable`
- `expiry_tracker.get_urgent`
- `expiry_tracker.get_expired`
- `expiry_tracker.get_between`

Example automation response query:

```yaml
action: expiry_tracker.get_actionable
data:
  important_only: false
  limit: 50
response_variable: admin_due
```

## Notifications and escalation

In integration options, set a Home Assistant notification service such as `notify.mobile_app_phone`. An optional target may also be supplied. Leave the service blank to keep built-in dispatch disabled and drive notifications entirely from automations using the sensors/actions.

Per-item policy supports warning thresholds, first-actionable, urgent, and expiry notifications, acknowledgement, repeat-until-acknowledged, and a repeat interval. Each transition is deduplicated. The scheduler checks hourly; non-repeat events are recorded once, while repeat attention messages respect the configured interval and stop after acknowledgement. Notification history is bounded with the rest of item history.

## Assist / LLM access

Expiry Tracker contributes a read-only `query_expiry_items` tool where supported by Home Assistant's contributed LLM APIs. It supports:

- `actionable_only`, `urgent_only`, and `expired_only`
- `due_within_days`
- category and important-only filters
- name/alias/category search

The tool prompt explicitly tells the model to use `actionable_only` for “what do I need to deal with?” questions. Mutation is intentionally unavailable to LLMs.

Examples include:

- “When does my passport expire?”
- “When can I renew my passport?”
- “What admin do I need to deal with?”
- “What becomes actionable this month?”
- “What expires in the next six months?”
- “Is anything urgent?”

## Example configurations

### Passport

- Category: Identity/document
- Expiry: the printed passport expiry
- Actionable: 9 months before expiry (to preserve travel-validity margin)
- Warnings: 365, 270, 180, 90, 30 days
- Urgent: 90 days
- Recurrence: manual or 10 years only if that reliably matches your renewal

### Car insurance

- Category: Insurance
- Actionable: 30 days before expiry, when renewal quotes are obtainable
- Warnings: 60, 30, 14, 7, 1 days
- Urgent: 7 days
- Recurrence: 12 months, if desired

### GP card

- Category: Medical
- Actionable: use the date on which renewal applications open, if known
- Warnings: 90, 30, 7 days
- Urgent: 7 days
- Acknowledgement: useful while supporting documents are being gathered

### Professional registration

- Category: Professional
- Actionable: immediately or from the renewal portal opening date
- Warnings: 180, 90, 30, 7 days
- Urgent: 30 days
- Important and require acknowledgement: enabled

## Storage, backup, and privacy

Records are stored through Home Assistant's versioned `.storage` mechanism and are included in normal Home Assistant backups. Writes are serialized and atomic at collection level. Storage migrations preserve records and are tested. A corrupt envelope or malformed record fails setup instead of silently replacing the collection with an empty one.

History is limited to 50 entries per item. Entity attributes and query limits are bounded. Diagnostics contain only counts, category totals, version information, and collection-wide options—never names, aliases, dates, notes, or history. There is no telemetry or external network dependency.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff format --check .
ruff check .
mypy custom_components/expiry_tracker
```

The repository is also structured for hassfest and HACS validation.
