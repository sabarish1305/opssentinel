import sys

from opssentinel.mcp_server import sign_rollback_approval_token


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/approve_rollback.py <plan_id>")
        raise SystemExit(1)

    plan_id = sys.argv[1]

    print()
    print("OpsSentinel - Human Recovery Approval")
    print("-------------------------------------")
    print(f"Rollback plan: {plan_id}")
    print()
    print("This approval authorizes one rollback plan for a limited time.")
    print("Type APPROVE to generate the approval token.")

    confirmation = input("> ").strip()

    if confirmation != "APPROVE":
        print("Approval denied.")
        raise SystemExit(1)

    try:
        token = sign_rollback_approval_token(plan_id)
    except RuntimeError as error:
        print(f"Approval failed: {error}")
        raise SystemExit(1)

    print()
    print("Approval granted.")
    print(f"Plan ID: {plan_id}")
    print(f"Approval token: {token}")


if __name__ == "__main__":
    main()