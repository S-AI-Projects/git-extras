import subprocess
import sys

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def main():
    print("=== Running Verification Check ===", flush=True)
    
    # Tool versions check
    rc, stdout, stderr = run_cmd("git --version && bats --version")
    print(f"[Tool Versions]\n{stdout.strip()}", flush=True)
    
    # Run targeted bats test for git-locked
    print("\n[Running git-locked Bats Tests]", flush=True)
    rc, stdout, stderr = run_cmd("bats tests/git-locked.bats")
    print(stdout, flush=True)
    
    if rc != 0:
        print(f"git-locked tests failed with code {rc}", flush=True)
        print(stderr, flush=True)
        sys.exit(rc)
        
    print("=== Verification Passed Successfully ===", flush=True)

if __name__ == "__main__":
    main() 