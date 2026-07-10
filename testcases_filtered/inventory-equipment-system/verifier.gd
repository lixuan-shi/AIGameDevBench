extends Node

# Exercises the Inventory (stacking + capacity) and Equipment (bonus replace)
# systems. Each scored checkpoint targets one independent trap, so the
# unimplemented baseline fails the first -> noop=0. A partial implementation
# (e.g. stacking but no capacity, or equip but double-counting on re-equip)
# lands between 0 and 1. Fail-fast stable denominator.

const CHECKPOINTS := [
	"add_creates_slot",
	"stacking_same_id_no_new_slot",
	"capacity_blocks_new_stack_when_full",
	"equip_applies_bonus",
	"reequip_replaces_not_doubles",
	"unequip_removes_bonus",
]

var checks := []

func _ready() -> void:
	call_deferred("run_validation")

func _record(name: String, condition: bool, detail: String, expected = null, actual = null) -> bool:
	checks.append({"name": name, "pass": condition, "detail": detail, "expected": expected, "actual": actual})
	return condition

func _emit() -> void:
	var seen := {}
	for c in checks:
		seen[c.name] = true
	for n in CHECKPOINTS:
		if not seen.has(n):
			checks.append({"name": n, "pass": false, "detail": "not reached (an earlier checkpoint failed)", "expected": null, "actual": null})
	print(JSON.stringify({"assertions": checks}))
	get_tree().quit()

func run_validation() -> void:
	var inv = get_node_or_null("Main/Inventory")
	var eq = get_node_or_null("Main/Equipment")
	if inv == null or eq == null:
		_record("add_creates_slot", false, "Inventory or Equipment node not found",
			"both nodes", "inv=%s eq=%s" % [inv, eq])
		return _emit()

	inv.capacity = 3

	# 1. add creates a slot.
	var added = inv.add("potion", 2)
	if not _record("add_creates_slot", added == true and inv.slot_count() == 1 and inv.total_quantity() == 2,
			"add() must create a stack: returns true, 1 slot, quantity 2",
			"true, slots=1, qty=2",
			"%s, slots=%d, qty=%d" % [added, inv.slot_count(), inv.total_quantity()]):
		return _emit()

	# 2. stacking the same id does not consume a new slot.
	inv.add("potion", 3)
	if not _record("stacking_same_id_no_new_slot", inv.slot_count() == 1 and inv.total_quantity() == 5,
			"stacking the same id must keep 1 slot and sum quantities to 5",
			"slots=1, qty=5",
			"slots=%d, qty=%d" % [inv.slot_count(), inv.total_quantity()]):
		return _emit()

	# 3. capacity blocks a new distinct stack when full.
	inv.add("ether", 1)   # slot 2
	inv.add("elixir", 1)  # slot 3 -> now full (capacity 3)
	var overflow = inv.add("bomb", 1)  # new id, no free slot -> rejected
	if not _record("capacity_blocks_new_stack_when_full",
			overflow == false and inv.slot_count() == 3,
			"a new stack must be rejected when all slots are full",
			"add=false, slots=3",
			"add=%s, slots=%d" % [overflow, inv.slot_count()]):
		return _emit()

	# 4. equip applies a bonus.
	eq.equip("weapon", 10)
	if not _record("equip_applies_bonus", eq.total_bonus == 10,
			"equipping must apply the bonus", 10, eq.total_bonus):
		return _emit()

	# 5. re-equipping the same slot replaces, not doubles.
	eq.equip("weapon", 15)
	if not _record("reequip_replaces_not_doubles", eq.total_bonus == 15,
			"re-equipping a slot must replace the bonus (15), not add (25)",
			15, eq.total_bonus):
		return _emit()

	# 6. unequip removes the bonus.
	eq.unequip("weapon")
	if not _record("unequip_removes_bonus", eq.total_bonus == 0,
			"unequipping must remove the slot's bonus", 0, eq.total_bonus):
		return _emit()

	_emit()
