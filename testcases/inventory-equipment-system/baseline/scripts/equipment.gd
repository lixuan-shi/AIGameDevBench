extends Node
class_name Equipment

# Equips one item per slot and tracks the total attack bonus.
# Contract:
#   - equip(slot, bonus): equips into `slot`. If something is already in that
#     slot, its bonus is removed first (no stale bonus), then the new bonus is
#     applied. total_bonus reflects the sum of currently-equipped slots.
#   - unequip(slot): removes whatever is in that slot and its bonus.
#   - equipping the same slot twice must NOT double-count (the old bonus is
#     replaced, not added on top).
#
# BASELINE: unimplemented stubs.

var total_bonus: int = 0
var _slots: Dictionary = {}  # slot -> bonus

func equip(slot: String, bonus: int) -> void:
	# TODO: replace any existing bonus in this slot, then apply the new one.
	pass

func unequip(slot: String) -> void:
	# TODO: remove the slot's bonus.
	pass
