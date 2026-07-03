extends Node

# Verifies the player FSM transition contract. Boots scenes/main.tscn (instanced
# as child "Main"), builds three states (idle/run/jump) with allowed-transition
# sets, and drives the StateMachine. Every scored checkpoint requires the guard
# AND enter()/exit() calls, so the buggy baseline (bare swap) fails the first
# one -> score 0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"legal_transition_calls_exit_and_enter",
	"legal_transition_returns_true_and_updates_current",
	"illegal_transition_rejected",
	"illegal_transition_no_side_effects",
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

func _make_state(sname: String, allowed: Array) -> PlayerState:
	var s := PlayerState.new()
	s.state_name = sname
	s.allowed = allowed
	return s

func run_validation() -> void:
	var sm = get_node_or_null("Main/StateMachine")
	if sm == null:
		_record("legal_transition_returns_true", false, "Main/StateMachine not found", "StateMachine", "null")
		return _emit()

	var idle := _make_state("idle", ["run", "jump"])
	var run := _make_state("run", ["idle", "jump"])
	var jump := _make_state("jump", ["idle"])  # cannot jump while jumping
	sm.register(idle)
	sm.register(run)
	sm.register(jump)
	sm.set_initial("idle")

	# Legal transition idle -> run. Check enter/exit FIRST so the buggy baseline
	# (which swaps current without enter/exit) fails the first scored checkpoint.
	var ok = sm.change_state("run")
	if not _record("legal_transition_calls_exit_and_enter",
			idle.exit_count == 1 and run.enter_count == 1,
			"change_state must call exit() on the old state and enter() on the new",
			"idle.exit=1, run.enter=1",
			"idle.exit=%d, run.enter=%d" % [idle.exit_count, run.enter_count]):
		return _emit()

	if not _record("legal_transition_returns_true_and_updates_current",
			ok == true and sm.current == run,
			"a legal transition must return true and update current to the new state",
			"true, current=run",
			"%s, current=%s" % [ok, (sm.current.state_name if sm.current else "null")]):
		return _emit()

	# Now in run; go to jump (legal), then attempt jump -> jump (illegal).
	sm.change_state("jump")
	var jump_enter_before := jump.enter_count
	var jump_exit_before := jump.exit_count
	var illegal = sm.change_state("jump")
	if not _record("illegal_transition_rejected", illegal == false and sm.current == jump,
			"an illegal transition (jump->jump) must return false and not change current",
			"false, current=jump",
			"%s, current=%s" % [illegal, (sm.current.state_name if sm.current else "null")]):
		return _emit()

	if not _record("illegal_transition_no_side_effects",
			jump.enter_count == jump_enter_before and jump.exit_count == jump_exit_before,
			"a rejected transition must not call enter()/exit()",
			"enter/exit unchanged",
			"enter %d->%d, exit %d->%d" % [jump_enter_before, jump.enter_count, jump_exit_before, jump.exit_count]):
		return _emit()

	_emit()
