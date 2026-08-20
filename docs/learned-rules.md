# EverStory — Symbolic World-Model Induction

Dynamics rules are **learned from interaction trajectories** `(state, action, next-state)`, not written by hand. Predicates are abstracted over action roles (`<item>`, `<target>`, `<destination>`, ...) so rules generalize across entities.

## Learned rules

- **give**: valid if [at(<item>,inventory) ∧ at(<recipient>,<here>) ∧ owner(<item>,<actor>)]; effects: +owner(<item>,<recipient>); -owner(<item>,<actor>); time +0
- **move**: valid if [connected(<here>,<destination>) ∧ connected(<destination>,<here>)]; effects: +at(<actor>,<destination>); time +1
- **open** (composite; induced per item-target pair):
  - ` -> chest`: valid if [at(<target>,<here>) ∧ not locked(<target>)]; effects: +at(flint,<here>); -at(flint,<target>); -contains(<target>,flint); time +0
- **take**: valid if [at(<item>,<here>)]; effects: +at(<item>,inventory); +owner(<item>,<actor>); -at(<item>,<here>); -unowned(<item>); time +0
- **use** (composite; induced per item-target pair):
  - `flint -> lantern`: valid if [at(<item>,inventory) ∧ filled(<target>) ∧ owner(<item>,<actor>)]; effects: +flag(lighthouse lit); +lit(<target>); -not flag(lighthouse lit); -not lit(<target>); time +0
  - `oil_can -> lantern`: valid if [at(<item>,inventory) ∧ at(<target>,<here>) ∧ not filled(<target>) ∧ not lit(<target>) ∧ owner(<item>,<actor>) ∧ unowned(<target>)]; effects: +filled(<target>); -not filled(<target>); time +0
  - `rusty_key -> chest`: valid if [at(<item>,inventory) ∧ at(<target>,<here>) ∧ key for(<target>,<item>) ∧ locked(<target>) ∧ owner(<item>,<actor>) ∧ unowned(<target>)]; effects: +not locked(<target>); -locked(<target>); time +0

## Prediction accuracy

- **All data**: 38/38 (100.0%) transitions predicted correctly.
- **Held-out episode** (light_the_lighthouse, trained only on the other two): 17/17 (100.0%).

Per action type (all data):

| Action | correct / total |
| --- | --- |
| `give` | 2/2 |
| `move` | 21/21 |
| `open` | 3/3 |
| `take` | 7/7 |
| `use` | 5/5 |

## Counterfactual checks (predictions on a fresh world)

- take the rusty key while standing in the cottage: **False** (expected False (the key is in the sea cave))
- move to the dock from the cottage: **True** (expected True (the dock is connected))

## Limitations (honest)

- The inducer learns **necessary conditions**: preconditions are the conjunction that separates observed successes from observed failures. Rarely-exercised preconditions may be missing.
- Effects that touch entities outside the action's params (e.g. `open` revealing the flint) stay concrete rather than abstracted.
- `use`/`open` are attribute-driven composite handlers, so their rules are induced per item-target pair instead of one global rule.
