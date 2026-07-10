extends Node
class_name Inventory

@export var capacity: int = 3

var _stacks: Dictionary = {}  # item_id -> quantity

func add(item_id: String, qty: int) -> bool:
	# TODO: implement
	return false

func total_quantity() -> int:
	# TODO
	return 0

func slot_count() -> int:
	# TODO
	return 0
