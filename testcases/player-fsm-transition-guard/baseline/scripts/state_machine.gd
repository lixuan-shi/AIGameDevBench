extends Node
class_name PlayerStateMachine

# Holds the player states and the active one. change_state(name) must:
#   - reject the transition if the current state does not allow it
#     (return false, change nothing, call no enter/exit);
#   - otherwise call exit() on the current state, enter() on the new state,
#     update `current`, and return true.
#
# BASELINE (buggy): change_state just swaps `current` with no guard and no
# enter()/exit() calls.

var states: Dictionary = {}
var current: PlayerState = null

func register(state: PlayerState) -> void:
	states[state.state_name] = state

func set_initial(name: String) -> void:
	current = states.get(name)
	if current != null:
		current.enter()

func change_state(target_name: String) -> bool:
	# TODO: guard with current.can_transition_to(), call exit()/enter().
	current = states.get(target_name)
	return true
