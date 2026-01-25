"""Set up cron job for daily digest."""

import os
import sys
from pathlib import Path

def get_cron_command() -> str:
    """Generate the cron command."""
    # Get the Python interpreter path
    python_path = sys.executable
    
    # Get the script path
    script_dir = Path(__file__).parent
    run_script = script_dir / "run_digest.py"
    
    # Get the project root for PYTHONPATH
    project_root = script_dir.parent
    
    # Build the command
    command = (
        f"cd {project_root} && "
        f"PYTHONPATH={project_root} "
        f"{python_path} {run_script} run "
        f">> {project_root}/logs/digest.log 2>&1"
    )
    
    return command


def main() -> None:
    """Print instructions for setting up cron."""
    command = get_cron_command()
    
    print("=" * 60)
    print("Cron Setup Instructions")
    print("=" * 60)
    
    print("\n1. Create logs directory:")
    print("   mkdir -p logs")
    
    print("\n2. Open crontab for editing:")
    print("   crontab -e")
    
    print("\n3. Add this line (runs at 7 AM daily):")
    print(f"\n   0 7 * * * {command}")
    
    print("\n4. Save and exit")
    
    print("\n" + "-" * 60)
    print("Alternative: Run every 6 hours")
    print("-" * 60)
    print(f"\n   0 */6 * * * {command}")
    
    print("\n" + "-" * 60)
    print("To verify cron is set up:")
    print("-" * 60)
    print("   crontab -l")
    
    print("\n" + "-" * 60)
    print("To test the command manually:")
    print("-" * 60)
    print(f"   {command}")


if __name__ == "__main__":
    main()
