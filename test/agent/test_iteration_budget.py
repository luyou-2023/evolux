from agent.iteration_budget import IterationBudget


def test_iteration_budget_consume_until_exhausted():
    budget = IterationBudget(max_total=3)
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False
    assert budget.used == 3
    assert budget.remaining == 0


def test_iteration_budget_refund():
    budget = IterationBudget(max_total=2)
    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False
    budget.refund()
    assert budget.consume() is True
    assert budget.remaining == 0
