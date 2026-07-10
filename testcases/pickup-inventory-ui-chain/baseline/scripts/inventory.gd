extends Node
class_name Inventory


signal inventory_changed(new_count: int)

var count: int = 0
var _seen_ids: Array = []

func add_item() -> void:
	count += 1

func collect_pickup(id: int) -> void:
	add_item()
