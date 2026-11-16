"""Small, explicit read models for the International Graphics workspace."""

import frappe
from frappe import _
from frappe.utils import add_days, today, getdate
from frappe.query_builder.functions import Coalesce, Sum
from pypika import Order
from frappe.database.query import RawCriterion
from crm.ig_extensions.permissions.customer_scope import scope_condition
from crm.ig_extensions.permissions.call_log import query_condition as call_scope

from crm.ig_extensions.permissions.profile import require_crm_role as get_session_role_flags
from crm.ig_extensions.api.sales_orders import _query as order_query, _available as orders_available
from crm.ig_extensions.permissions.sales_scope import visible_users


def _count(doctype, filters=None):
	if not frappe.has_permission(doctype, "read"):
		return 0
	rows = frappe.get_list(doctype, fields=[{"COUNT": "name", "as": "count"}], filters=filters or {})
	return int(rows[0].count) if rows else 0


@frappe.whitelist()
def get_products(txt: str = "", start: int = 0, limit: int = 30):
	get_session_role_flags()
	if not frappe.db.exists("DocType", "Item") or not frappe.has_permission("Item", "read"):
		return {"rows": [], "total": 0}
	filters = {"disabled": 0, "is_sales_item": 1}
	search = [["item_code", "like", "%" + txt.strip() + "%"], ["item_name", "like", "%" + txt.strip() + "%"]] if txt else None
	rows = frappe.get_list("Item", fields=["name", "item_code", "item_name", "item_group", "stock_uom", "image"],
		filters=filters, or_filters=search, order_by="item_name asc, name asc", limit=min(max(int(limit), 1), 100), offset=max(int(start), 0))
	counts = frappe.get_list("Item", fields=[{"COUNT": "name", "as": "count"}], filters=filters, or_filters=search)
	stocks = get_stock([row.name for row in rows])
	for row in rows:
		row["stock"] = stocks.get(row.name, {"status": "unknown"})
	return {"rows": rows, "total": int(counts[0].count) if counts else 0}


@frappe.whitelist()
def get_product(name: str):
	get_session_role_flags()
	frappe.has_permission("Item", "read", doc=name, throw=True)
	item = frappe.get_doc("Item", name)
	prices = []
	if frappe.has_permission("Item Price", "read"):
		prices = frappe.get_list("Item Price", fields=["price_list", "price_list_rate", "currency", "uom", "valid_from", "valid_upto"],
			filters={"item_code": name, "selling": 1, "customer": ["is", "not set"], "supplier": ["is", "not set"]}, order_by="price_list asc", limit=30)
	return {**{key: item.get(key) for key in ["name", "item_code", "item_name", "item_group", "stock_uom", "description", "image", "disabled", "is_stock_item"]}, "prices": prices, "stock": get_stock([name]).get(name, {"status": "unknown"})}


@frappe.whitelist()
def get_overview(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	get_session_role_flags()
	start, end = getdate(from_date or add_days(today(), -30)), getdate(to_date or today())
	if start > end:
		frappe.throw(_("The start date must be before the end date."), frappe.ValidationError)
	allowed = visible_users()
	if user and allowed is not None and user not in allowed:
		frappe.throw(_("This salesperson is outside your authorized team."), frappe.PermissionError)
	# Selecting one salesperson narrows the already-permissioned query, never changes session rights.
	order_args = dict(from_date=str(start), to_date=str(end))
	orders = frappe.qb.DocType("Sales Order")
	def oq(fields, **kwargs):
		query = order_query(fields, **order_args, **kwargs)
		return query.where(orders.owner == user) if user else query
	states, trend, products = [], [], []
	if orders_available():
		states = oq(["docstatus", {"COUNT": "name", "as": "count"}], group_by="docstatus").run(as_dict=True)
		trend = oq(["transaction_date", {"COUNT": "name", "as": "count"}], group_by="transaction_date", order_by="transaction_date asc").run(as_dict=True)
		items = frappe.qb.DocType("Sales Order Item")
		products = frappe.qb.from_(items).select(items.item_code, items.item_name, items.uom, Sum(items.qty).as_("qty")).where(
			items.parent.isin(oq(["name"])) & (items.parenttype == "Sales Order") & (items.parentfield == "items")
		).groupby(items.item_code, items.item_name, items.uom).orderby(Sum(items.qty), order=Order.desc).limit(6).run(as_dict=True)
	calls = frappe.qb.DocType("CRM Call Log")
	call_rows = []
	if frappe.has_permission("CRM Call Log", "read"):
		outcome_fields = ["call_outcome"] if frappe.get_meta("CRM Call Log").has_field("call_outcome") else []
		query = frappe.qb.get_query("CRM Call Log", fields=["caller", "receiver", "type", "owner", "status", *outcome_fields, {"COUNT": "name", "as": "count"}, {"SUM": "duration", "as": "duration"}],
			group_by="caller, receiver, type, owner, status" + (", call_outcome" if outcome_fields else ""), ignore_permissions=False)
		query = query.where(Coalesce(calls.start_time, calls.creation).between(str(start) + " 00:00:00", str(end) + " 23:59:59.999999"))
		if condition := call_scope():
			query = query.where(RawCriterion(condition))
		if user:
			query = query.where(((calls.type == "Outgoing") & (calls.caller == user)) | ((calls.type == "Incoming") & (calls.receiver == user)) |
				((Coalesce(calls.caller, "") == "") & (Coalesce(calls.receiver, "") == "") & (calls.owner == user)))
		call_rows = query.run(as_dict=True)
	agents, outcomes, technical_statuses = {}, {}, {}
	for row in call_rows:
		outcome = row.get("call_outcome") or ""
		outcomes[outcome] = outcomes.get(outcome, 0) + int(row.count)
		technical_statuses[row.status] = technical_statuses.get(row.status, 0) + int(row.count)
		agent = (row.caller if row.type == "Outgoing" else row.receiver) or row.owner
		entry = agents.setdefault(agent, {"user": agent, "calls": 0, "completed": 0, "duration": 0})
		entry["calls"] += int(row.count)
		entry["completed"] += int(row.count) if row.status == "Completed" else 0
		entry["duration"] += float(row.duration or 0)
	for entry in agents.values():
		entry["label"] = frappe.db.get_value("User", entry["user"], "full_name") or entry["user"] or _("Unassigned")
	portfolio = frappe.qb.get_query("CRM Organization", fields=[{"COUNT": "name", "as": "count"}], ignore_permissions=False)
	if user or allowed is not None:
		portfolio = portfolio.where(RawCriterion(scope_condition("CRM Organization", user or frappe.session.user)))
	portfolio_rows = portfolio.run(as_dict=True)
	customers = int(portfolio_rows[0].count) if portfolio_rows else 0
	return {"from_date": str(start), "to_date": str(end), "orders": sum(int(row.count) for row in states),
		"states": {str(row.docstatus): int(row.count) for row in states}, "trend": trend, "products": products,
		"calls": sum(entry["calls"] for entry in agents.values()), "completed": sum(entry["completed"] for entry in agents.values()),
		"duration": sum(entry["duration"] for entry in agents.values()), "agents": sorted(agents.values(), key=lambda row: -row["calls"]),
		"customers": customers, "catalog_products": _count("Item", {"disabled": 0, "is_sales_item": 1}) if frappe.db.exists("DocType", "Item") else 0,
		"outcomes": [{"label": (frappe.db.get_value("Call Outcome", key, "title") or key) if key and frappe.db.exists("DocType", "Call Outcome") else _("Sin resultado comercial registrado"), "count": count} for key, count in outcomes.items()],
		"technical_statuses": [{"label": key, "count": count} for key, count in technical_statuses.items()]}


@frappe.whitelist()
def get_stock(names: list[str]):
	get_session_role_flags()
	items = frappe.get_list("Item", filters={"name": ["in", names[:100]]}, fields=["name", "stock_uom", "is_stock_item"], limit=100)
	result = {item.name: {"status": "unknown" if item.is_stock_item else "not_stock", "uom": item.stock_uom, "warehouses": []} for item in items}
	if not frappe.has_permission("Bin", "read") or not frappe.has_permission("Warehouse", "read"):
		for item in items:
			if item.is_stock_item:
				result[item.name]["status"] = "restricted"
		return result
	warehouses = frappe.get_list("Warehouse", filters={"is_group": 0, "disabled": 0}, pluck="name", limit=0)
	if not warehouses:
		return result
	bins = frappe.get_list("Bin", fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty", "modified"], filters={"item_code": ["in", list(result)], "warehouse": ["in", warehouses]}, limit=0, order_by="warehouse asc")
	for row in bins:
		result[row.item_code]["warehouses"].append(row)
	for stock in result.values():
		if stock["warehouses"]:
			stock["status"] = "known"
			stock["actual_qty"] = sum(row.actual_qty for row in stock["warehouses"])
	return result


@frappe.whitelist()
def get_sales_users():
	get_session_role_flags()
	names = set(frappe.get_all("Has Role", filters={"role": ["in", ["Sales User", "Sales Manager", "System Manager"]]}, pluck="parent"))
	names.add("Administrator")
	if (allowed := visible_users()) is not None:
		names.intersection_update(allowed)
	return [{"value": row.name, "label": row.full_name} for row in frappe.get_all("User", filters={"name": ["in", list(names)], "enabled": 1}, fields=["name", "full_name"], order_by="full_name asc")]
