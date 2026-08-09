import sys
from pathlib import Path

# Resolve project root (two levels up from src/nextcloud_init/)
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

# Import the 4 Day 0 initialization steps
import src.nextcloud_init.step_00_seed_taxonomy as step00
import src.nextcloud_init.step_01_bulk_ingest as step01
import src.nextcloud_init.step_02_build_knowledge as step02
import src.nextcloud_init.step_03_deploy_prefect as step03


def main():
    print("="*60)
    print("🌟 MASTER DAY 0 BOOTSTRAP SEQUENCE (STEPS 00 -> 03)")
    print("="*60)
    
    step00.main()
    
    step01.main()
    
    step02.main()
    
    step03.main()

    print("\n" + "="*60)
    print("🎉 NEXTCLOUD INITIAL SETUP COMPLETE!")
    print("   All 4 initial phases executed. System is live for BAU!")
    print("="*60)

if __name__ == "__main__":
    main()