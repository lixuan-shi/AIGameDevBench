extends Node
class_name GameController

# Orchestrates waves of enemies, scoring, and win detection.
# Contract:
#   - wave_sizes[i] = number of enemies in wave i.
#   - start(): begin wave 0, creating its enemies (as Enemy children of self),
#     connecting each enemy's `died` to the controller.
#   - when an enemy dies: award score and increment the combo counter; when the
#     whole current wave is dead, advance to the next wave (spawning it). After
#     the LAST wave is fully cleared, emit game_won (once) and set won = true.
#   - Scoring: each kill is worth 10 + 5*(combo-1), where combo is how many
#     kills have happened SO FAR in the run (1 for the first kill, 2 for the
#     second, ...). So kills score 10, 15, 20, 25, ...
#   - alive_count() returns living enemies in the current wave.
#   - the verifier kills enemies by calling kill_one() which damages the first
#     living enemy of the current wave for lethal damage.
#
# BASELINE: unimplemented.

signal game_won

@export var wave_sizes: Array[int] = [2, 3]

var score: int = 0
var combo: int = 0
var current_wave: int = -1
var won: bool = false

var _enemies: Array = []

func start() -> void:
	# TODO: spawn wave 0, wire up deaths.
	pass

func alive_count() -> int:
	# TODO
	return 0

func kill_one() -> void:
	# TODO: deal lethal damage to the first living enemy of the current wave.
	pass
