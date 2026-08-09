import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

def main():
    print("="*60)
    print("📅 NEXTCLOUD INIT STEP 3: PREFECT FLOW SCHEDULE DEPLOYMENT")
    print("="*60)

    # Deploy daily master workflow
    print("\nDeploying Daily Ingestion Flow (1:00 AM)...")
    subprocess.run([sys.executable, "flows/unified_flow.py"], check=True)

    # Deploy weekly taxonomy proposal workflow
    print("\nDeploying Weekly Taxonomy Proposal Flow (Sunday 1:00 AM)...")
    subprocess.run([sys.executable, "flows/agent_proposal_flow.py"], check=True)

    print("\n" + "="*60)
    print("🎉 Prefect Deployments Complete. Day N automation is now ACTIVE!")
    print("="*60)

if __name__ == "__main__":
    main()