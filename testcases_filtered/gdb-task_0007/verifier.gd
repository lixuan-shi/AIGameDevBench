# Converted from GameDevBench task_0007 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

var signal_counts: Array[int] = []

const CHECKPOINTS := [
    "cards_is_array",
    "new_pile_empty",
    "add_emits_new_counts",
    "cards_appended",
    "draw_removes_front",
    "draw_emits_new_size",
    "shuffle_preserves_contents",
    "to_string_enumerates",
    "clear_emits_zero",
    "empty_after_clear",
    "draw_empty_returns_null",
]

var checks := []

func _ready():
    run_validation()

func make_card(id: String, cost: int = 1) -> Card:
    var card = Card.new()
    card.id = id
    card.cost = cost
    return card

func _capture_signal(count: int) -> void:
    signal_counts.append(count)

func _record(name: String, condition: bool, detail: String,
        expected = null, actual = null) -> bool:
    checks.append({"name": name, "pass": condition, "detail": detail,
        "expected": expected, "actual": actual})
    return condition

func _emit() -> void:
    var seen := {}
    for c in checks:
        seen[c.name] = true
    for n in CHECKPOINTS:
        if not seen.has(n):
            checks.append({"name": n, "pass": false,
                "detail": "not reached (an earlier checkpoint failed)",
                "expected": null, "actual": null})
    print(JSON.stringify({"assertions": checks}))
    get_tree().quit()

func run_validation() -> void:
    var card_pile_script: GDScript = load("res://scripts/card_pile.gd")
    var pile = card_pile_script.new() as Resource
    if not _record("cards_is_array", pile.cards is Array,
            "cards export must be an Array", "Array", typeof(pile.cards)):
        return _emit()
    if not _record("new_pile_empty", pile.empty(),
            "New CardPile should be empty", true, pile.empty()):
        return _emit()
    pile.card_pile_size_changed.connect(_capture_signal)

    var strike = make_card("strike", 1)
    var defend = make_card("defend", 1)
    pile.add_card(strike)
    pile.add_card(defend)
    if not _record("add_emits_new_counts", signal_counts == [1, 2],
            "Add should emit new counts", [1, 2], signal_counts):
        return _emit()
    if not _record("cards_appended", pile.cards.size() == 2,
            "Cards not appended correctly", 2, pile.cards.size()):
        return _emit()

    var drawn = pile.draw_card()
    if not _record("draw_removes_front", drawn == strike,
            "draw_card must remove from the front", "the front card (strike)",
            ("strike" if drawn == strike else str(drawn))):
        return _emit()
    if not _record("draw_emits_new_size", signal_counts[-1] == 1,
            "draw_card must emit new size after removal", 1, signal_counts[-1]):
        return _emit()

    pile.shuffle()
    if not _record("shuffle_preserves_contents",
            pile.cards.size() == 1 and pile.cards[0] == defend,
            "shuffle should preserve contents", "[defend] (size 1)",
            "size %d" % pile.cards.size()):
        return _emit()

    var bash = make_card("bash", 2)
    pile.add_card(bash)
    var listing = pile._to_string()
    if not _record("to_string_enumerates", listing == "1: defend\n2: bash",
            "_to_string should enumerate cards", "1: defend\n2: bash", listing):
        return _emit()

    pile.clear()
    if not _record("clear_emits_zero", signal_counts[-1] == 0,
            "clear() must emit 0 size", 0, signal_counts[-1]):
        return _emit()
    if not _record("empty_after_clear", pile.empty(),
            "CardPile should be empty after clear", true, pile.empty()):
        return _emit()
    var drawn_empty = pile.draw_card()
    if not _record("draw_empty_returns_null", drawn_empty == null,
            "draw_card on empty pile should return null", null, drawn_empty):
        return _emit()

    _emit()
