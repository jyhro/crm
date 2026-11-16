import frappe
from frappe import _
from frappe.database.query import RawCriterion
from crm.ig_extensions.permissions.profile import require_crm_role
from crm.ig_extensions.permissions.call_log import query_condition as call_scope
from crm.ig_extensions.permissions.note import query_condition as note_scope


@frappe.whitelist()
def get_notes(start: int = 0, txt: str = ""):
	require_crm_role()
	filters = {"title": ["like", "%" + txt + "%"]} if txt else {}
	query = frappe.qb.get_query("FCRM Note", fields=["name", "title", "content", "modified", "owner", "reference_doctype", "reference_docname"], filters=filters, order_by="modified desc, name desc", offset=max(int(start), 0), limit=30, ignore_permissions=False)
	if scope := note_scope():
		query = query.where(RawCriterion(scope))
	rows = query.run(as_dict=True)
	return {"rows": rows, "calls": get_note_calls([row.name for row in rows]), "has_more": len(rows) == 30}


@frappe.whitelist()
def get_note_calls(names: list[str]):
	require_crm_role()
	names = names[:100]
	query = frappe.qb.get_query("FCRM Note", fields=["name", "reference_doctype", "reference_docname"], filters={"name": ["in", names]}, limit=100, ignore_permissions=False)
	if scope := note_scope():
		query = query.where(RawCriterion(scope))
	notes = query.run(as_dict=True)
	allowed = [row.name for row in notes]
	links = frappe.get_all("Dynamic Link", filters={"parenttype": "CRM Call Log", "link_doctype": "FCRM Note", "link_name": ["in", allowed]}, fields=["parent", "link_name"])
	ids = {row.parent for row in links} | {row.reference_docname for row in notes if row.reference_doctype == "CRM Call Log" and row.reference_docname}
	call_table = frappe.qb.DocType("CRM Call Log")
	query = frappe.qb.get_query("CRM Call Log", fields=["name", "start_time", "type", "status", "duration", "note"], limit=200, ignore_permissions=False)
	query = query.where(call_table.name.isin(list(ids)) | call_table.note.isin(allowed))
	# Query's OR applies to ID/note linkage, while the outer scope stays mandatory.
	if scope := call_scope():
		query = query.where(RawCriterion(scope))
	calls = query.run(as_dict=True)
	result = {name: [] for name in allowed}
	for row in notes:
		linked_ids = {link.parent for link in links if link.link_name == row.name}
		if row.reference_doctype == "CRM Call Log":
			linked_ids.add(row.reference_docname)
		result[row.name] = [call for call in calls if call.name in linked_ids or call.note == row.name]
	return result


@frappe.whitelist(methods=["POST"])
def add_note_to_call_log(call_sid: str, note: dict):
	call = frappe.get_doc("CRM Call Log", call_sid, for_update=True)
	call.check_permission("write")
	if note.get("name"):
		doc = frappe.get_doc("FCRM Note", note["name"], for_update=True)
		doc.check_permission("write")
		if note.get("content") is not None and doc.content != note["content"]:
			from crm.ig_extensions.api.orders import _version
			_version(doc, note.get("modified"))
			doc.content = note["content"]
	else:
		doc = frappe.get_doc({"doctype": "FCRM Note", "title": note.get("title") or _("Nota de llamada"), "content": note.get("content")})
	if not doc.reference_docname:
		doc.reference_doctype, doc.reference_docname = "CRM Call Log", call_sid
	doc.save()
	call.link_with_reference_doc("FCRM Note", doc.name)
	call.save()
	return doc.as_dict()
