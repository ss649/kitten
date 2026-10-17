import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="kitten",
        description="Kitten: Automated Property-Based Testing (PBT) Pipeline",
    )

    parser.add_argument(
        "--pbt",
        action="store_true",
        help="Run property-based testing on the target Python file.",
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the Python file to test.",
    )

    args = parser.parse_args()

    if not args.file or not args.pbt:
        parser.print_help()
        sys.exit(0)

    if not os.path.exists(args.file):
        print(f"Error: Target file '{args.file}' does not exist.")
        sys.exit(1)

    print(f"[*] Running Kitten PBT pipeline on: {args.file}")

    try:
        from src.graph import graph

        initial_state = {"file_path": args.file}
        config = {"configurable": {"thread_id": "cli_run"}}
        final_state = graph.invoke(initial_state, config=config)

        stage = final_state.get("stage")
        status = final_state.get("verification_status")
        extracted = final_state.get("extracted_functions", [])
        pbt_results = final_state.get("pbt_results", [])
        error = final_state.get("error")

        print("\n" + "=" * 50)
        print("                  PIPELINE SUMMARY")
        print("=" * 50)
        print(f"Pipeline Stage      : {stage}")
        print(f"Verification Status : {status}")
        print(f"Functions Extracted : {len(extracted)}")

        for func in extracted:
            print(f"  - {func.get('name')}")

        print("-" * 50)
        print("PBT Test Results:")

        for result in pbt_results:
            func_name = result.get("function_name", "unknown")
            res_status = result.get("status", "UNKNOWN")
            counterexample = result.get("counterexample")
            err_msg = result.get("error_message")

            print(f"\n  Function: {func_name}")
            print(f"  Result  : {res_status}")

            if res_status != "PASSED":
                if counterexample:
                    print(f"  Counterexample: {counterexample}")
                if err_msg:
                    print(f"  Error Detail  : {err_msg}")

        print("=" * 50)

        if error:
            print(f"\n[!] Pipeline Error: {error}")
            sys.exit(1)

        if status == "PASSED":
            print("\n[+] All properties verified successfully!")
            sys.exit(0)
        else:
            print("\n[-] Some properties failed or were not verified.")
            sys.exit(1)

    except Exception as e:
        print(f"\n[!] Fatal execution error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
