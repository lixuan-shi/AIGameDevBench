extends Node
class_name PlayerStateMachine



var states: Dictionary = {}
var current: PlayerState = null

func register(state: PlayerState) -> void:
	states[state.state_name] = state

func set_initial(name: String) -> void:
	current = states.get(name)
	if current != null:
		current.enter()

func change_state(target_name: String) -> bool:
	current = states.get(target_name)
	return true
