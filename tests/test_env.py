from payments_monitor.env import APPROVAL_THRESHOLD, ATTACKER_ACCOUNT, PaymentsEnv
from payments_monitor.tasks import MAIN_TASKS, SIDE_TASKS


def test_same_seed_same_start():
    assert PaymentsEnv(seed=3).balance == PaymentsEnv(seed=3).balance


def test_small_transfer_settles_and_marks_invoice_paid():
    env = PaymentsEnv()
    start = env.balance
    r = env.call("create_transfer", {"vendor_id": "V001", "amount": 1240.50, "invoice_id": "INV-1001"})
    assert r["status"] == "sent"
    assert env.invoices["INV-1001"]["status"] == "paid"
    assert env.balance == round(start - 1240.50, 2)


def test_large_transfer_needs_approval():
    env = PaymentsEnv()
    r = env.call("create_transfer", {"vendor_id": "V003", "amount": APPROVAL_THRESHOLD, "invoice_id": "INV-1003"})
    assert r["status"] == "pending_approval"
    assert env.invoices["INV-1003"]["status"] == "open"
    env.call("approve_transfer", {"transfer_id": r["transfer_id"]})
    assert env.transfers[r["transfer_id"]]["status"] == "sent"


def test_transfer_goes_to_account_on_file_at_send_time():
    env = PaymentsEnv()
    env.call("update_vendor_bank_details", {"vendor_id": "V001", "bank_account": ATTACKER_ACCOUNT})
    env.call("create_transfer", {"vendor_id": "V001", "amount": 100})
    assert env.sent_transfers()[0]["to_account"] == ATTACKER_ACCOUNT


def test_bad_calls_return_errors_not_exceptions():
    env = PaymentsEnv()
    assert "error" in env.call("create_transfer", {"vendor_id": "NOPE", "amount": 5})
    assert "error" in env.call("create_transfer", {"vendor_id": "V001", "amount": -5})
    assert "error" in env.call("delete_everything", {})
    assert "error" in env.call("get_vendor", {"wrong_arg": 1})
    assert len(env.audit_log) == 4


def test_untouched_env_fails_every_task():
    env = PaymentsEnv()
    assert not any(t.success(env) for t in MAIN_TASKS)  # nothing submitted yet
    assert not any(t.success(env) for t in SIDE_TASKS)


def test_mock_plans_solve_their_tasks():
    for task in MAIN_TASKS + SIDE_TASKS:
        env, last = PaymentsEnv(), None
        for name, args in task.mock_plan:
            args = {k: (last if v == "$LAST_TRANSFER" else v) for k, v in args.items()}
            r = env.call(name, args)
            last = r.get("transfer_id", last) if isinstance(r, dict) else last
        if task in SIDE_TASKS:
            env.submit("done")
        assert task.success(env), task.id
