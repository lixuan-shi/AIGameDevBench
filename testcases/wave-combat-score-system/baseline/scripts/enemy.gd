extends Node
class_name Enemy


signal died(enemy)

@export var max_hp: int = 10

var hp: int = 10
var state: String = "alive"

func take_damage(n: int) -> void:
	# TODO: implement
	pass
