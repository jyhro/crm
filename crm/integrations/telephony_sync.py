import frappe

SYNCED_FIELDS = (
	"type",
	"status",
	"from",
	"to",
	"recording_url",
	"start_time",
	"end_time",
)


def mirror_tp_call_log(doc, method=None):
	"""Keep a `CRM Call Log` in sync with the telephony app's `TP Call Log`.

	Twilio webhooks are handled by the telephony app, which only writes `TP Call Log`;
	the CRM UI reads and annotates `CRM Call Log` under the same call SID.
	"""
	values = {field: doc.get(field) for field in SYNCED_FIELDS}
	values.update(
		{
			"caller": doc.caller or None,
			"receiver": doc.receiver or None,
			"duration": int(doc.duration or 0),
			"telephony_medium": doc.telephony_medium or "Twilio",
		}
	)

	if frappe.db.exists("CRM Call Log", doc.name):
		call_log = frappe.get_doc("CRM Call Log", doc.name)
		call_log.update(values)
	else:
		call_log = frappe.get_doc({"doctype": "CRM Call Log", "id": doc.name, **values})
		link_with_lead_or_deal(call_log)

	call_log.save(ignore_permissions=True)


def link_with_lead_or_deal(call_log):
	from crm.integrations.twilio.api import link

	contact_number = call_log.get("from") if call_log.type == "Incoming" else call_log.get("to")
	if not contact_number:
		return
	try:
		link(contact_number, call_log)
	except Exception:
		# linking is a convenience; never block the call over it
		frappe.log_error(title="Error while linking mirrored call log")
