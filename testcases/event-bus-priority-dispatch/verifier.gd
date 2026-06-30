extends Node

# Exercises the EventBus: priority ordering, tie insertion-order, unsubscribe,
# re-subscribe (priority update), and safe removal before dispatch. Each scored
# checkpoint inspects dispatch_log. Baseline stubs -> empty log -> fails first ->
# noop=0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"dispatch_in_priority_order",
	"ties_keep_insertion_order",
	"unsubscribe_removes_subscriber",
	"resubscribe_updates_priority",
	"publish_removing_is_safe",
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

func _log_of(bus) -> Array:
	var out: Array = []
	for x in bus.dispatch_log:
		out.append(String(x))
	return out

func run_validation() -> void:
	var bus = get_node_or_null("Main/EventBus")
	if bus == null:
		_record("dispatch_in_priority_order", false, "Main/EventBus not found", "EventBus", "null")
		return _emit()

	# Priority order: subscribe out of order; higher priority dispatched first.
	bus.subscribe("C", 1)
	bus.subscribe("A", 3)
	bus.subscribe("B", 2)
	bus.publish()
	if not _record("dispatch_in_priority_order", _log_of(bus) == ["A", "B", "C"],
			"publish must dispatch high->low priority", ["A", "B", "C"], _log_of(bus)):
		return _emit()

	# Ties keep insertion order: add X then Y at priority 2 (same as B).
	bus.subscribe("X", 2)
	bus.subscribe("Y", 2)
	bus.publish()
	# Expected: A(3), then the three priority-2 in insertion order B,X,Y, then C(1).
	if not _record("ties_keep_insertion_order", _log_of(bus) == ["A", "B", "X", "Y", "C"],
			"ties must dispatch in subscription order",
			["A", "B", "X", "Y", "C"], _log_of(bus)):
		return _emit()

	# Unsubscribe removes.
	bus.unsubscribe("X")
	bus.unsubscribe("Y")
	bus.unsubscribe("B")
	bus.publish()
	if not _record("unsubscribe_removes_subscriber", _log_of(bus) == ["A", "C"],
			"unsubscribed ids must not be dispatched", ["A", "C"], _log_of(bus)):
		return _emit()

	# Re-subscribe updates priority: bring B back at priority 5 (now highest).
	bus.subscribe("B", 5)
	bus.publish()
	if not _record("resubscribe_updates_priority", _log_of(bus) == ["B", "A", "C"],
			"re-subscribing updates priority (B now highest)", ["B", "A", "C"], _log_of(bus)):
		return _emit()

	# Safe removal before dispatch: publish_removing("A") drops A only.
	bus.publish_removing("A")
	if not _record("publish_removing_is_safe", _log_of(bus) == ["B", "C"],
			"publish_removing must drop only the removed id, keeping order",
			["B", "C"], _log_of(bus)):
		return _emit()

	_emit()
