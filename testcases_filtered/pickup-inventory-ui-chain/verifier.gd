extends Node

# Verifies the pickup -> inventory -> UI signal chain. Boots scenes/main.tscn
# (instanced as child "Main"). Binds the HUD label to the inventory, then drives
# collect_pickup() calls. The first scored checkpoint requires the label to
# update (signal wired + bind implemented), which the baseline does not do, so
# noop=0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"label_updates_on_first_pickup",
	"count_is_one_after_first_pickup",
	"idempotent_on_repeated_pickup_id",
	"distinct_pickup_id_increments",
	"label_matches_count_after_chain",
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
	var inventory = get_node_or_null("Main/Inventory")
	var label = get_node_or_null("Main/HUD/CountLabel")
	if inventory == null or label == null:
		_record("label_updates_on_first_pickup", false, "Inventory or CountLabel not found",
			"both nodes", "inv=%s label=%s" % [inventory, label])
		return _emit()

	label.bind(inventory)

	# First pickup (id 1): the label must reflect the new count via the signal.
	inventory.collect_pickup(1)
	if not _record("label_updates_on_first_pickup", label.text == "1",
			"HUD label must update to the inventory count when a pickup is collected",
			"1", label.text):
		return _emit()

	if not _record("count_is_one_after_first_pickup", inventory.count == 1,
			"inventory count must be 1 after the first pickup", 1, inventory.count):
		return _emit()

	# Re-collect the SAME pickup id: must be idempotent (no double count).
	inventory.collect_pickup(1)
	if not _record("idempotent_on_repeated_pickup_id",
			inventory.count == 1 and label.text == "1",
			"re-collecting the same pickup id must not change the count",
			"count=1, label=1", "count=%d, label=%s" % [inventory.count, label.text]):
		return _emit()

	# A distinct pickup id increments.
	inventory.collect_pickup(2)
	if not _record("distinct_pickup_id_increments",
			inventory.count == 2 and label.text == "2",
			"a new pickup id must increment the count and update the label",
			"count=2, label=2", "count=%d, label=%s" % [inventory.count, label.text]):
		return _emit()

	if not _record("label_matches_count_after_chain", label.text == str(inventory.count),
			"the label must equal the inventory count after the full chain",
			str(inventory.count), label.text):
		return _emit()

	_emit()
