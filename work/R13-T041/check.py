import os
import sys
import shutil
import tempfile
import subprocess

def run_tests():
    print("--- Running Command Contract & Native Tests for git-bulk ---")

    # 1. PATH setup: Prepend bin/ to PATH
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    bin_path = os.path.join(repo_root, "bin")
    
    env = os.environ.copy()
    env["PATH"] = f"{bin_path}:{env.get('PATH', '')}"

    # Verify git-bulk binary is accessible
    git_bulk_bin = shutil.which("git-bulk", path=env["PATH"])
    if not git_bulk_bin:
        print("ERROR: bin/git-bulk not found in PATH.")
        sys.exit(1)

    print(f"Using git-bulk at: {git_bulk_bin}")

    # 2. Setup isolated temporary directory for HOME & Git repos
    temp_dir = tempfile.mkdtemp(prefix="git_bulk_test_")
    env["HOME"] = temp_dir  # Isolate global workspace list

    try:
        # Create a valid git repository inside temp dir
        repo_dir = os.path.join(temp_dir, "test_repo")
        os.makedirs(repo_dir, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Test 1: Ordinary Success Case (Run valid Git command 'status' via git-bulk)
        res_success = subprocess.run(
            ["git-bulk", "-a", "status"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env
        )
        print(f"Success Case (git-bulk -a status) Exit Code: {res_success.returncode}")

        # Test 2: Failure Case (Unknown/Invalid Git command)
        res_fail = subprocess.run(
            ["git-bulk", "-a", "invalid_non_existent_cmd_99"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env
        )
        print(f"Failure Case (Invalid command) Exit Code: {res_fail.returncode}")

        # --- ASSERTIONS ---
        if res_success.returncode != 0:
            print("ASSERTION ERROR: Success test case did not return 0.")
            print("STDOUT:", res_success.stdout)
            print("STDERR:", res_success.stderr)
            sys.exit(1)

        if res_fail.returncode == 0:
            print("ASSERTION ERROR: Failure test case unexpectedly returned 0.")
            sys.exit(1)

        print("\nSUCCESS: All command contract assertions passed successfully!")
        sys.exit(0)

    finally:
        # Cleanup isolated temp folder
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_tests()