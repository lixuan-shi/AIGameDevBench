extends Node
class_name PlayerState

# A player state. Tracks enter/exit calls and declares which states it may
# transition to. Subclasses set `state_name` and `allowed`.

var state_name: String = ""
var allowed: Array = []
var enter_count: int = 0
var exit_count: int = 0

func enter() -> void:
	enter_count += 1

func exit() -> void:
	exit_count += 1

func can_transition_to(target_name: String) -> bool:
	return allowed.has(target_name)
