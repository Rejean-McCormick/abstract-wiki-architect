import csv
import os
import sys
import time

# Add project root to path so we can import 'router'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

import router  # noqa: E402


def run_universal_tests():
    print("========================================")
    print("   UNIVERSAL TEST RUNNER v1.0           ")
    print("========================================")

    test_dir = os.path.join(current_dir, "generated_datasets")

    if not os.path.exists(test_dir):
        print(f"❌ Error: Test directory not found: {test_dir}")
        print("   Run 'test_suite_generator.py' first.")
        return

    files = [f for f in os.listdir(test_dir) if f.endswith(".csv")]

    if not files:
        print("⚠️  No CSV files found. Please generate tests first.")
        return

    # Global Stats
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    start_time = time.time()

    for filename in files:
        # Extract language code from filename (test_suite_it.csv -> it)
        # Format is typically "test_suite_{code}.csv"
        try:
            lang_code = filename.replace("test_suite_", "").replace(".csv", "")
        except ValueError:
            print(f"⚠️  Skipping malformed filename: {filename}")
            continue

        print(f"\n📂 Processing Suite: {filename} [{lang_code.upper()}]")

        filepath = os.path.join(test_dir, filename)
        file_passed = 0
        file_failed = 0

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Verify headers exist
            if "Name" not in reader.fieldnames:
                print("   ❌ Invalid CSV format. Missing 'Name' column.")
                continue

            # Find the dynamic column names for lemmas
            # They usually look like "Profession_Lemma_in_Italian"
            prof_col = next(
                (c for c in reader.fieldnames if c.startswith("Profession_Lemma")), None
            )
            nat_col = next(
                (c for c in reader.fieldnames if c.startswith("Nationality_Lemma")),
                None,
            )

            if not prof_col or not nat_col:
                print("   ❌ Could not identify Lemma columns.")
                continue

            for row in reader:
                test_id = row.get("Test_ID", "Unknown")
                expected = row.get("EXPECTED_FULL_SENTENCE", "").strip()

                # Inputs
                name = row["Name"]

                # Safely get gender from either possible column name
                gender = row.get("Gender") or row.get("Gender (Male/Female)", "Unknown")

                # Clean brackets from inputs: "[Actor]" -> "Actor"
                prof_input = row[prof_col].replace("[", "").replace("]", "").strip()
                nat_input = row[nat_col].replace("[", "").replace("]", "").strip()

                # Skip if data is missing (User hasn't filled the CSV yet)
                if not prof_input or not expected:
                    total_skipped += 1
                    continue

                # --- CALL THE ROUTER ---
                try:
                    # The router picks the right engine (Romance, Slavic, etc.) automatically
                    actual = router.render_biography(
                        name, gender, prof_input, nat_input, lang_code
                    )

                    if actual == expected:
                        file_passed += 1
                        total_passed += 1
                        # print(f"   ✅ {test_id}: PASS") # Uncomment for verbose output
                    else:
                        file_failed += 1
                        total_failed += 1
                        print(f"   ❌ {test_id}: FAIL")
                        print(
                            f"      Input:    {name} ({gender}) | {prof_input} | {nat_input}"
                        )
                        print(f"      Expected: {expected}")
                        print(f"      Actual:   {actual}")

                except Exception as e:
                    print(f"   🔥 CRASH {test_id}: {str(e)}")
                    file_failed += 1
                    total_failed += 1

        # File Summary
        if file_passed + file_failed > 0:
            rate = (file_passed / (file_passed + file_failed)) * 100
            print(
                f"   📊 Result: {file_passed} Passed, {file_failed} Failed ({rate:.1f}%)"
            )
        else:
            print("   ⚠️  No active test cases found (Fill in the CSVs!)")

    # Final Report
    duration = time.time() - start_time
    print("\n========================================")
    print(f"   TEST RUN COMPLETE in {duration:.2f}s")
    print("========================================")
    print(f"✅ Total Passed:  {total_passed}")
    print(f"❌ Total Failed:  {total_failed}")
    print(f"⏭️  Total Skipped: {total_skipped}")

    if total_failed == 0 and total_passed > 0:
        print("\n🏆 SYSTEM STABLE. Ready for Wikifunctions deployment.")
    elif total_passed == 0:
        print(
            "\n💤 No tests ran. Please populate 'EXPECTED_FULL_SENTENCE' in the CSVs."
        )


if __name__ == "__main__":
    run_universal_tests()
