# Converted from GameDevBench task_0013 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

class DummyState:
    extends State
    var entered := false
    var exited := false
    func _init(actor: Node) -> void:
        super(actor)
    func enter() -> void:
        entered = true
    func exit() -> void:
        exited = true

const CHECKPOINTS := [
    "state_stashes_actor",
    "fsm_has_state_changed_signal",
    "change_state_updates_active",
    "change_state_calls_enter",
    "change_state_calls_exit",
    "change_state_enters_replacement",
    "state_changed_emits_per_transition",
]

var checks := []

func _ready() -> void:
    load("res://components/state.gd")
    load("res://components/finite_state_machine.gd")
    run_validation()

func _record(name: String, condition: bool, detail: String,
        expected = null, actual = null) -> bool:
    checks.append({"name": name, "pass": condition, "detail": detail,
        "expected": expected, "actual": actual})
    return condition

func _emit() -> void:
    var seen := {}
    for c in checks:
        seen[c.name] = true
    for n in CHECKPOINTS:
        if not seen.has(n):
            checks.append({"name": n, "pass": false,
                "detail": "not reached (an earlier checkpoint failed)",
                "expected": null, "actual": null})
    print(JSON.stringify({"assertions": checks}))
    get_tree().quit()

func run_validation() -> void:
    var actor := Node.new()
    var state := State.new(actor)
    if not _record("state_stashes_actor", state.actor == actor,
            "State must stash the actor passed to _init",
            "the actor passed to _init", str(state.actor)):
        return _emit()

    var fsm := FiniteStateMachine.new()
    if not _record("fsm_has_state_changed_signal", fsm.has_signal("state_changed"),
            "FiniteStateMachine needs a state_changed signal",
            true, fsm.has_signal("state_changed")):
        return _emit()

    var first := DummyState.new(actor)
    var second := DummyState.new(actor)
    var signals := []
    fsm.state_changed.connect(func(new_state: State): signals.append(new_state))

    fsm.change_state(first)
    if not _record("change_state_updates_active", fsm.state == first,
            "change_state must update the active state",
            "the new state", str(fsm.state)):
        return _emit()
    if not _record("change_state_calls_enter", first.entered,
            "change_state should call enter() on the new state",
            true, first.entered):
        return _emit()

    fsm.change_state(second)
    if not _record("change_state_calls_exit", first.exited,
            "change_state should call exit() on the outgoing state",
            true, first.exited):
        return _emit()
    if not _record("change_state_enters_replacement", second.entered,
            "change_state must enter the replacement state",
            true, second.entered):
        return _emit()
    if not _record("state_changed_emits_per_transition", signals.size() == 2,
            "state_changed must emit for every transition",
            2, signals.size()):
        return _emit()

    _emit()
