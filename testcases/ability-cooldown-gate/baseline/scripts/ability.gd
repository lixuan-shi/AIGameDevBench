extends Node
class_name Ability

# An ability with a cooldown. After use(), it must not be usable again until
# `cooldown` seconds have elapsed (advanced via tick()).
#
# BASELINE (unimplemented): use() does nothing to gate re-use and can_use()
# always returns true, so the ability can fire every frame.

@export var cooldown: float = 1.0

var _time_remaining: float = 0.0

func can_use() -> bool:
	return true

func use() -> bool:
	# TODO: only succeed when off cooldown, and start the cooldown on success.
	return true

func tick(delta: float) -> void:
	# TODO: advance the cooldown timer.
	pass
