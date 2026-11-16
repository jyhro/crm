import frappe
from frappe import _
from crm.ig_extensions.permissions.sales_scope import visible_users, user_condition
from crm.ig_extensions.permissions.customer_scope import _responsible
from crm.ig_extensions.permissions.call_log import agent_condition


def condition(user=None):
	return (
		f"({user_condition('`tabFCRM Note`.owner', user)}"
		" OR (`tabFCRM Note`.reference_doctype = 'CRM Lead' AND EXISTS (SELECT 1 FROM `tabCRM Lead` lead"
		f" WHERE lead.name = `tabFCRM Note`.reference_docname AND {_responsible('lead', 'lead_owner', 'CRM Lead', user or frappe.session.user)}))"
		" OR (`tabFCRM Note`.reference_doctype = 'CRM Deal' AND EXISTS (SELECT 1 FROM `tabCRM Deal` deal"
		f" WHERE deal.name = `tabFCRM Note`.reference_docname AND {_responsible('deal', 'deal_owner', 'CRM Deal', user or frappe.session.user)}))"
		" OR EXISTS (SELECT 1 FROM `tabCRM Call Log` WHERE "
		"((`tabFCRM Note`.reference_doctype = 'CRM Call Log' AND `tabCRM Call Log`.name = `tabFCRM Note`.reference_docname)"
		" OR `tabCRM Call Log`.note = `tabFCRM Note`.name OR EXISTS (SELECT 1 FROM `tabDynamic Link` linked"
		" WHERE linked.parenttype = 'CRM Call Log' AND linked.parent = `tabCRM Call Log`.name"
		" AND linked.link_doctype = 'FCRM Note' AND linked.link_name = `tabFCRM Note`.name))"
		f" AND ({agent_condition(user)})))"
	)


def query_condition(user=None):
	return "" if visible_users(user) is None else condition(user)


def can_access(name, user=None):
	return visible_users(user) is None or bool(frappe.db.sql(f"SELECT name FROM `tabFCRM Note` WHERE name = %s AND ({condition(user)})", (name,)))


def has_permission(doc, ptype, user=None, **kwargs):
	if doc.is_new() or ptype == "create" or can_access(doc.name, user):
		return True
	frappe.throw(_("You can only access notes in your authorized portfolio."), frappe.PermissionError)
