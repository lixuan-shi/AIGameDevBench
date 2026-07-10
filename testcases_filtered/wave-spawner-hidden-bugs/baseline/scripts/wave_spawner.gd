extends Node
class_name WaveSpawner

signal wave_started(index: int, size: int)
signal all_waves_cleared

@export var wave_sizes: Array[int] = [3, 5, 4]

var current_wave: int = -1
var live: int = 0
var spawned_total: int = 0
var finished: bool = false

func start() -> void:
	current_wave = 0
	_spawn_current_wave()

func _spawn_current_wave() -> void:
	var size: int = wave_sizes[current_wave]
	for i in range(size - 1):
		live += 1
		spawned_total += 1
	wave_started.emit(current_wave, size)

func notify_enemy_killed() -> void:
	if finished:
		return
	live -= 1
	if live < 0:
		_advance()

func _advance() -> void:
	if current_wave + 1 >= wave_sizes.size():
		current_wave += 1
		_spawn_current_wave()
