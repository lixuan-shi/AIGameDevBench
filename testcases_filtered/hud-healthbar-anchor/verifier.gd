extends SceneTree

# visual_static runs in --script mode (extends SceneTree), so this script loads
# and instantiates the HUD scene itself and inspects the HealthBar's anchors.
# The contract: the HealthBar must be anchored to the TOP-RIGHT corner
# (anchor_left == anchor_right == 1.0, anchor_top == anchor_bottom == 0.0) so it
# stays pinned to the right on window resize, rather than positioned by raw
# top-left offsets. Every scored checkpoint requires a right-edge anchor, which
# the baseline (default 0 anchors) fails -> noop=0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"healthbar_anchored_to_right_edge",
	"healthbar_anchored_to_top",
	"healthbar_not_left_anchored",
]

var checks := []

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
	quit()

func _init() -> void:
	run_validation()

func run_validation() -> void:
	var packed = load("res://scenes/hud.tscn")
	if packed == null:
		_record("healthbar_anchored_to_right_edge", false, "could not load res://scenes/hud.tscn", "PackedScene", "null")
		return _emit()
	var hud = packed.instantiate()
	var bar = hud.get_node_or_null("HealthBar")
	if bar == null:
		_record("healthbar_anchored_to_right_edge", false, "HealthBar node not found in HUD", "HealthBar", "null")
		return _emit()

	var eps := 0.001
	# Right edge: both left and right anchors at 1.0 pin the bar to the right.
	if not _record("healthbar_anchored_to_right_edge",
			abs(bar.anchor_left - 1.0) < eps and abs(bar.anchor_right - 1.0) < eps,
			"HealthBar must be anchored to the right edge (anchor_left and anchor_right == 1.0)",
			"anchor_left=1.0, anchor_right=1.0",
			"anchor_left=%s, anchor_right=%s" % [bar.anchor_left, bar.anchor_right]):
		return _emit()

	if not _record("healthbar_anchored_to_top",
			abs(bar.anchor_top - 0.0) < eps and abs(bar.anchor_bottom - 0.0) < eps,
			"HealthBar must be anchored to the top (anchor_top and anchor_bottom == 0.0)",
			"anchor_top=0.0, anchor_bottom=0.0",
			"anchor_top=%s, anchor_bottom=%s" % [bar.anchor_top, bar.anchor_bottom]):
		return _emit()

	# Guard against the baseline default (left-anchored): anchor_left must not be 0.
	if not _record("healthbar_not_left_anchored", abs(bar.anchor_left - 0.0) > eps,
			"HealthBar must not be left-anchored (anchor_left == 0 is the resize-breaking default)",
			"anchor_left != 0", bar.anchor_left):
		return _emit()

	_emit()
