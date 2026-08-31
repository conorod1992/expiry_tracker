# Expiry Tracker

Expiry Tracker is a Home Assistant custom integration for keeping track of things that expire or need renewing.

It can be used for things such as:

- Passports and driving licences
- Insurance policies
- Medical or GP cards
- Professional registrations
- Pet licences
- Certificates
- Warranties
- Domains and subscriptions
- Almost anything else with an expiry or renewal date

Expiry Tracker does more than tell you **what expires next**. It can also tell you **what actually needs your attention now**.

For example, your passport might expire in nine months, but if you can renew it now, Expiry Tracker can already treat it as something you can deal with. Another item might expire sooner but not be renewable yet.

Everything is stored locally in Home Assistant. Expiry Tracker does not require an account or external cloud service.

## Features

- Dedicated **Expiry Tracker** page in the Home Assistant sidebar
- Warning, actionable, urgent and expiry dates
- Clear **Needs your attention**, **Coming up** and **Later** sections
- Search, filtering and sorting
- Completion and renewal history
- Optional Home Assistant notifications
- Optional repeating reminders until you dismiss them
- Home Assistant sensors and calendar
- Optional sensor for each individual item
- Actions for use in automations
- Read-only Assist/LLM access where supported
- Local storage with no telemetry or external network access

---

## Installation

### HACS

Expiry Tracker can be installed as a custom repository in HACS.

1. Open **HACS** in Home Assistant.
2. Open the **⋮** menu in the top-right corner.
3. Select **Custom repositories**.
4. Enter:

   `https://github.com/conorod1992/expiry_tracker`

5. Select **Integration** as the repository type.
6. Select **Add**.
7. Find **Expiry Tracker** in HACS and install it.
8. Restart Home Assistant when prompted.
9. Go to **Settings → Devices & services**.
10. Select **Add integration**.
11. Search for **Expiry Tracker** and add it.

Expiry Tracker will then appear in the Home Assistant sidebar.

> If Expiry Tracker does not appear when searching for it after installation, first make sure Home Assistant has been restarted. Refreshing or clearing your browser cache can also help after installing a new custom integration.

### Manual installation

Download or copy the `expiry_tracker` integration folder into:

```text
config/custom_components/expiry_tracker
```

The final folder should therefore contain files such as:

```text
config/
└── custom_components/
    └── expiry_tracker/
        ├── __init__.py
        ├── manifest.json
        └── ...
```

Restart Home Assistant, then go to:

**Settings → Devices & services → Add integration**

Search for **Expiry Tracker** and add it.

---

# Getting started

Once installed, open **Expiry Tracker** from the Home Assistant sidebar and select the option to add your first item.

For most items, you only need to decide:

1. **What is it?**
2. **When does it expire?**
3. **When would you like advance warning?**
4. **When can you actually do something about it?**
5. **When should it become urgent?**

The last two are optional, but they are what allow Expiry Tracker to distinguish between something that is simply approaching its expiry date and something that genuinely needs attention.

## A simple example

Suppose a passport expires on **30 November**.

You might configure:

- **Expiry:** 30 November
- **Actionable:** 9 months before expiry
- **Warning:** 12 months before expiry
- **Urgent:** 3 months before expiry

Expiry Tracker can then distinguish between:

**Warning**  
> Your passport is getting closer to expiry, but you may not need to do anything yet.

**Ready to deal with**  
> Renewal is now possible, so this is something you can act on.

**Urgent**  
> The expiry is getting close and should receive higher priority.

**Expired**  
> The expiry date has passed.

You do not have to use every stage. The settings can be as simple or detailed as you need.

---

# Understanding statuses

Every enabled item has one current status.

| Status | What it means |
|---|---|
| **All good** | Nothing needs attention yet. |
| **Coming up** | A warning period has begun, but you cannot or do not need to act yet. |
| **Ready to deal with** | The item has reached the date from which you can take action. |
| **Urgent** | The item is close enough to expiry to be treated as higher priority. |
| **Expired** | The expiry date has passed. |

Internally these correspond to `valid`, `warning`, `actionable`, `urgent` and `expired`.

### Expiry date

The expiry date is the **last date on which the item is still valid**.

For example, something with an expiry date of 30 November becomes expired on 1 December.

### Warning

Warnings give you advance notice.

You can have several warning points, such as:

- 180 days
- 90 days
- 30 days
- 7 days
- 1 day

A warning does **not** necessarily mean that action can already be taken.

### Actionable

The actionable date answers:

> **When can I actually start dealing with this?**

You can configure this as:

- Immediately
- A number of days before expiry
- A number of months before expiry
- A specific date

For example, if an insurance company only provides renewal quotes 30 days before expiry, you could make the policy actionable 30 days before its expiry date.

### Urgent

The urgent date is when an outstanding item should move to a higher level of priority.

Urgent takes precedence over actionable.

---

# The sidebar

Expiry Tracker organises items by what you are likely to need next rather than presenting one large administration table.

## Needs your attention

Contains items which are actionable, urgent or expired and currently need attention.

These items provide quick actions such as:

- The configured completion action, such as **Mark as renewed** or **Mark as checked**
- **Dismiss reminder**

## Dismissed — still outstanding

Dismissing a reminder does **not** complete the underlying task.

It simply tells Expiry Tracker that you do not want to be reminded about that particular stage again.

The item remains visible here because the underlying expiry is still outstanding.

If it later reaches another stage—for example, moving from **Ready to deal with** to **Urgent**—it can ask for your attention again.

## Expired — no action needed

Items configured for informational tracking only can expire without becoming work you need to complete. They are kept in a separate informational section and do not create an attention reminder to dismiss.

## Coming up

Contains enabled items which are approaching their warning, actionable or expiry dates.

High-priority items may also appear here.

## Later / inactive

Contains items which are further away, together with disabled items.

This keeps them available without allowing distant dates to dominate the main view.

## Archived items

Archived items keep their history but no longer take part in active reminders, sensors, calendar entries or expiry views.

An archived item can be reopened later without recreating it or losing its history.

---

# Adding and editing items

The item editor is divided into sections so that common settings appear first and more specialised options can be left alone unless needed.

## Basic details

Set the item's name, category, expiry date and other basic information.

## When can you deal with it?

This controls the **actionable date**.

Use it when an item cannot or does not need to be dealt with immediately.

For example:

- Passport renewal opens 9 months before expiry
- Insurance quotes become available 30 days before expiry
- A professional registration portal opens on a particular date

If there is no waiting period, you can simply allow the item to be dealt with **Any time**.

## Reminders

You can create one or more advance warning points.

Common values are available as presets, or you can enter your own number of days.

With built-in notifications, **Repeat until dismissed** can keep repeating the current actionable, urgent or expiry reminder until you dismiss that stage. When the optional Reminders integration handles delivery, snoozing, dismissal and escalation are managed there instead.

## Action & repeat

Choose what completing the real-world task means for the item. Expiry Tracker supports common actions such as renew, replace, review, re-test, re-register and check, plus custom wording.

For actions that continue tracking the item, you can configure a typical repeat period so Expiry Tracker can suggest the next expiry date after completion. The date is **never changed automatically**.

For **Cancel / end**, completing the task archives the item while retaining its history instead of asking for another expiry date.

## Advanced

Less commonly needed options are kept here, including search aliases, the optional per-item Home Assistant sensor and whether the item is active.

---

# Example setups

These are examples rather than rules. Actual renewal periods and requirements vary, so configure dates to suit the item you are tracking.

## Passport

Example:

- **Category:** Identity/document
- **Expiry:** Date printed on the passport
- **Actionable:** 9 months before expiry
- **Warnings:** 365, 270, 180, 90 and 30 days
- **Urgent:** 90 days
- **Renewal period:** Manual, or 10 years if that reliably matches the passport concerned

Using an earlier actionable date can be useful where you want to preserve a travel-validity margin rather than waiting until the passport is close to expiry.

## Car insurance

Example:

- **Category:** Insurance
- **Expiry:** Current policy end date
- **Actionable:** 30 days before expiry
- **Warnings:** 60, 30, 14, 7 and 1 days
- **Urgent:** 7 days
- **Renewal period:** 12 months, if appropriate

## GP or medical card

Example:

- **Category:** Medical
- **Expiry:** Card expiry date
- **Actionable:** The date renewal applications open, if known
- **Warnings:** 90, 30 and 7 days
- **Urgent:** 7 days

## Professional registration

Example:

- **Category:** Professional
- **Actionable:** Immediately, or from the date the renewal portal opens
- **Warnings:** 180, 90, 30 and 7 days
- **Urgent:** 30 days
- **High priority:** Enabled if appropriate

---

# Dismissing and completing

These actions deliberately mean different things.

### Dismiss reminder

Use this when:

> “I know about this. Stop reminding me about this stage for now.”

The expiry date is unchanged and the real-world task is **not** recorded as complete.

Dismissal applies only to the current stage.

For example, dismissing the actionable reminder does not prevent the item from becoming urgent later.

### Complete the configured action

Use the completion action only when the real-world task has actually been completed—for example, when an item has been renewed, replaced, reviewed or checked.

For actions that continue tracking the item, Expiry Tracker will:

- Record the previous expiry in the item's history
- Ask you to confirm the next expiry date
- Reset its reminder/dismissal state
- Begin tracking the new expiry

A **Cancel / end** action archives the item instead of asking for a new expiry date.

---

# Notifications

Expiry Tracker can optionally send notifications through a normal Home Assistant `notify` service.

To configure built-in notifications:

1. Go to **Settings → Devices & services**.
2. Find **Expiry Tracker**.
3. Open its configuration/options.
4. Enter the notification service you want to use.

For example:

```text
notify.mobile_app_my_phone
```

You can leave this blank if you prefer to create your own Home Assistant automations using Expiry Tracker's sensors and actions.

Depending on the item settings, notifications can be sent for:

- Warning points
- First becoming actionable
- Becoming urgent
- Expiry

Notifications can optionally repeat until that stage is dismissed.

Expiry Tracker checks for notification changes hourly. It avoids repeatedly sending a one-off notification for the same transition.

---

# Optional Reminders integration

Expiry Tracker can also work with the separate **Reminders** integration when it is installed.

This is entirely optional. You do **not** need Reminders to use Expiry Tracker.

When the integration is available:

- Warning milestones are treated as informational reminders.
- Enabled actionable, urgent and expiry milestones remain outstanding until dismissed or the underlying task is completed.
- A completion action can take you back to Expiry Tracker to confirm the next expiry date when one is required.

Selecting a completion action from a Home Assistant notification does not silently change the expiry date. Expiry Tracker still asks you to confirm or edit the new date first when the item continues tracking.

---

# Home Assistant entities

You do not need to use these entities to use Expiry Tracker. They are provided for dashboards, templates and automations.

Expiry Tracker creates collection-level entities including:

| Entity | Purpose |
|---|---|
| `sensor.next_expiry` | The next enabled item to expire |
| `sensor.next_actionable_expiry` | The next outstanding item that can be acted on |
| `sensor.expiry_tracker_actionable` | Number of items requiring attention |
| `sensor.expiry_tracker_urgent` | Number of urgent items |
| `sensor.expiry_tracker_expired` | Number of expired items |
| `calendar.expiry_tracker` | Calendar containing enabled expiry dates |

## Per-item sensors

When **Create a Home Assistant sensor for this item** is enabled, Expiry Tracker also creates a date sensor for that particular item.

Its attributes include information such as:

- Expiry
- Days remaining
- Current status
- Actionable date
- Urgent date
- Dismissal state
- Category
- Importance

The item's internal ID remains the same if you rename it, so renaming an item does not make Expiry Tracker treat it as a completely new record.

---

# Using Expiry Tracker in automations

This section is optional and intended for users who want to integrate Expiry Tracker more deeply with Home Assistant.

Expiry Tracker provides actions for creating and changing items:

```text
expiry_tracker.create_item
expiry_tracker.update_item
expiry_tracker.delete_item
expiry_tracker.renew_item
expiry_tracker.close_item
expiry_tracker.reopen_item
expiry_tracker.acknowledge_item
expiry_tracker.reset_acknowledgement
```

`close_item` archives an item without deleting its history. `reopen_item` returns it to active tracking.

It also provides actions which return information:

```text
expiry_tracker.search_items
expiry_tracker.get_upcoming
expiry_tracker.get_actionable
expiry_tracker.get_urgent
expiry_tracker.get_expired
expiry_tracker.get_between
```

For example, an automation or script can retrieve all currently actionable items:

```yaml
action: expiry_tracker.get_actionable
data:
  important_only: false
  limit: 50
response_variable: admin_due
```

The returned data can then be used later in the automation or script.

Items are identified internally using a stable `item_id`. This means automations can continue referring to an item even if its displayed name changes.

---

# Assist and LLM access

This is an advanced optional feature.

Where supported by Home Assistant's LLM/Assist system, Expiry Tracker can provide a read-only `query_expiry_items` tool.

This allows a compatible conversation agent to answer questions such as:

- “When does my passport expire?”
- “When can I renew my passport?”
- “What admin do I need to deal with?”
- “What becomes actionable this month?”
- “What expires in the next six months?”
- “Is anything urgent?”

Queries can be filtered by things such as:

- Actionable items
- Urgent items
- Expired items
- Items due within a number of days
- Category
- High-priority items
- Name or alias

The LLM access is intentionally **read-only**. A conversation agent cannot use this tool to create, delete or renew your items.

---

# Dates and month offsets

When you configure an actionable or other date using calendar months, Expiry Tracker handles shorter months automatically.

For example:

**1 month before 31 March → 28 February**

or 29 February in a leap year.

This avoids invalid dates when moving between months of different lengths.

---

# Storage, backups and privacy

Expiry Tracker stores its information locally using Home Assistant's `.storage` system.

Its data is therefore included in normal Home Assistant backups.

Expiry Tracker does not require:

- An online account
- A separate cloud service
- Telemetry
- External network access

Diagnostics deliberately exclude personal item details such as:

- Names
- Aliases
- Expiry dates
- Notes
- History
- Custom category names
- Notification service and target identifiers

Diagnostics contain aggregate counts, counts for the built-in categories, integration/storage versions and non-sensitive collection-wide options. Notification identifiers are redacted, and custom categories are reported only as anonymous counts.

History is limited to 50 entries per item.

Expiry Tracker also validates its stored data during setup rather than silently replacing damaged or malformed data with an empty collection.

---

# Troubleshooting

## Expiry Tracker does not appear under Add integration

Make sure:

1. Expiry Tracker has been installed successfully through HACS or manually.
2. Home Assistant has been restarted.
3. The folder exists at:

```text
config/custom_components/expiry_tracker
```

If it was installed correctly but still does not appear in the integration search, refresh Home Assistant in your browser or clear the browser cache.

## The sidebar page does not appear

Try refreshing the Home Assistant frontend after installing and setting up the integration.

If necessary, restart Home Assistant and reload the browser.

## Notifications are not being sent

Check that the configured notification service exists in Home Assistant and is entered in the same form you would use in an automation, for example:

```text
notify.mobile_app_my_phone
```

You can test the notification service separately from **Developer tools → Actions**.

## I dismissed something but it is still shown

This is intentional.

**Dismiss reminder** means that the current reminder stage has been acknowledged. It does not mean that the underlying task has been completed.

The item remains outstanding until you complete its configured action, archive it or otherwise change it.

---

# Bugs and feature requests

If you find a problem or have an idea for Expiry Tracker, please open an issue on the GitHub repository:

https://github.com/conorod1992/expiry_tracker/issues

When reporting a bug, including the Home Assistant version, Expiry Tracker version and relevant logs or diagnostics can make the problem easier to investigate.

Please avoid including sensitive personal information in screenshots or logs.

---

# Development

The following section is intended for contributors rather than normal installation.

```bash
python -m pip install -e '.[dev]'
pytest
ruff format --check .
ruff check .
mypy custom_components/expiry_tracker
```

The repository is also structured for HACS and Home Assistant `hassfest` validation.