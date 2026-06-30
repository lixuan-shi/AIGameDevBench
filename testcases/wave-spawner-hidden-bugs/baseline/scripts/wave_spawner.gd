extends Node
class_name WaveSpawner

# Drives enemy waves. wave_sizes[i] is how many enemies wave i spawns.
# Contract:
#   - start() begins wave 0 and spawns its full size.
#   - notify_enemy_killed() decrements the live count; when the live count
#     reaches 0 it advances to the next wave and spawns it.
#   - after the LAST wave is cleared, emit all_waves_cleared (exactly once) and
#     set finished = true; no further wave is spawned.
#
# This baseline LOOKS complete and runs, but contains three subtle bugs that
# the task asks you to find and fix. (Do not assume it is correct just because
# it runs.)

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
	# BUG 1 (off-by-one): spawns size-1 enemies, so every wave is short by one.
	for i in range(size - 1):
		live += 1
		spawned_total += 1
	wave_started.emit(current_wave, size)

func notify_enemy_killed() -> void:
	if finished:
		return
	live -= 1
	# BUG 2 (boundary): advances while live < 0 instead of <= 0, so a wave never
	# actually advances on reaching zero.
	if live < 0:
		_advance()

func _advance() -> void:
	# BUG 3 (final wave): uses >= count to mean "more waves remain", so the last
	# wave is treated as if a further wave exists and all_waves_cleared never
	# fires; finished is never set.
	if current_wave + 1 >= wave_sizes.size():
		current_wave += 1
		_spawn_current_wave()
