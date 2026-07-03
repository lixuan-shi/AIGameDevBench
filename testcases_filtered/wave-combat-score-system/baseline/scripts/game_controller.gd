extends Node
class_name GameController

# Orchestrates waves of enemies, scoring, and win detection. See the task
# description for the required public API and behavior.

signal game_won

@export var wave_sizes: Array[int] = [2, 3]

var score: int = 0
var combo: int = 0
var current_wave: int = -1
var won: bool = false

var _enemies: Array = []

func start() -> void:
	# TODO: implement
	pass

func alive_count() -> int:
	# TODO
	return 0

func kill_one() -> void:
	# TODO: implement
	pass
