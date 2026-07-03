extends Node

# Drives the full wave/combat/score system end to end with wave_sizes [2,3]
# (5 kills scoring 10,15,20,25,30 = 100). Each checkpoint requires a different
# subsystem to work together (spawn, death->score, combo, wave advance, win,
# total). Baseline stubs fail the first -> noop=0. Partial implementations land
# in the middle. Fail-fast stable denominator.

const CHECKPOINTS := [
	"wave0_spawns_two",
	"first_kill_scores_ten",
	"combo_scoring_after_two_kills",
	"wave_advances_after_clear",
	"final_wave_clears_and_wins_once",
	"total_score_is_100",
]

var checks := []
var _won_count := 0

func _ready() -> void:
	call_deferred("run_validation")

func _record(name: String, condition: bool, detail: String, expected = null, actual = null) -> bool:
	checks.append({"name": name, "pass": condition, "detail": detail, "expected": expected, "actual": actual})
	return condition

func _emit() -> void:
	var seen := {}
	for c in checks:
		seen[c.name] = true
	for n in CHECKPOINTS:
		if not seen.has(n):
			checks.append({"name": n, "pass": false, "detail": "not reached (an earlier checkpoint failed)", "expected": null, "actual": null})
	print(JSON.stringify({"assertions": checks}))
	get_tree().quit()

func _on_won() -> void:
	_won_count += 1

func run_validation() -> void:
	var gc = get_node_or_null("Main/GameController")
	if gc == null:
		_record("wave0_spawns_two", false, "Main/GameController not found", "GameController", "null")
		return _emit()

	var sizes: Array[int] = [2, 3]
	gc.wave_sizes = sizes
	if gc.has_signal("game_won"):
		gc.game_won.connect(_on_won)

	gc.start()
	if not _record("wave0_spawns_two", gc.alive_count() == 2,
			"wave 0 must spawn 2 living enemies", 2, gc.alive_count()):
		return _emit()

	# Kill 1 -> score 10.
	gc.kill_one()
	if not _record("first_kill_scores_ten", gc.score == 10 and gc.alive_count() == 1,
			"first kill scores 10 and leaves 1 alive",
			"score=10, alive=1", "score=%d, alive=%d" % [gc.score, gc.alive_count()]):
		return _emit()

	# Kill 2 -> +15 -> 25; wave 0 now clear, should advance to wave 1 (3 alive).
	gc.kill_one()
	if not _record("combo_scoring_after_two_kills", gc.score == 25,
			"second kill adds 15 (combo) for total 25", 25, gc.score):
		return _emit()

	if not _record("wave_advances_after_clear",
			gc.current_wave == 1 and gc.alive_count() == 3,
			"clearing wave 0 must advance to wave 1 with 3 alive",
			"wave=1, alive=3", "wave=%d, alive=%d" % [gc.current_wave, gc.alive_count()]):
		return _emit()

	# Kill the remaining 3 (-> +20,+25,+30). Final wave clears -> win.
	gc.kill_one()
	gc.kill_one()
	gc.kill_one()
	if not _record("final_wave_clears_and_wins_once",
			gc.won == true and _won_count == 1,
			"after the final wave clears, won is true and game_won fired once",
			"won=true, signals=1", "won=%s, signals=%d" % [gc.won, _won_count]):
		return _emit()

	if not _record("total_score_is_100", gc.score == 100,
			"total score must be 10+15+20+25+30 = 100", 100, gc.score):
		return _emit()

	_emit()
