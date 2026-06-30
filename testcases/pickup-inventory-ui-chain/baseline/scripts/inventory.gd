extends Node
class_name Inventory

# Holds a count of collected items. add_item() must increase the count and emit
# inventory_changed(new_count). collect_pickup(id) records a pickup but must be
# idempotent per id (collecting the same pickup id twice does nothing).
#
# BASELINE (buggy): no signal emitted; collect_pickup is NOT idempotent.

signal inventory_changed(new_count: int)

var count: int = 0
var _seen_ids: Array = []

func add_item() -> void:
	# TODO: increment count and emit inventory_changed(count).
	count += 1

func collect_pickup(id: int) -> void:
	# TODO: ignore ids already collected; otherwise record and add_item().
	add_item()
