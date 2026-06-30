extends Node
class_name Inventory

# A slot-limited, stacking inventory.
# Contract:
#   - capacity is the max number of distinct SLOTS (stacks), not total items.
#   - add(item_id, qty): if a stack for item_id exists, increase its quantity
#     (no new slot). Otherwise, if a free slot exists, create a new stack.
#     If full and the item is not already stacked, return false and add nothing.
#     Returns true if anything was added.
#   - total_quantity() returns the sum of all stack quantities.
#   - slot_count() returns the number of occupied slots.
#
# BASELINE: unimplemented stubs.

@export var capacity: int = 3

var _stacks: Dictionary = {}  # item_id -> quantity

func add(item_id: String, qty: int) -> bool:
	# TODO: implement stacking + capacity per the contract.
	return false

func total_quantity() -> int:
	# TODO
	return 0

func slot_count() -> int:
	# TODO
	return 0
