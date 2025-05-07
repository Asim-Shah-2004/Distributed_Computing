import atexit
import subprocess
import logging
import os
from pathlib import Path
from colorama import init, Fore, Style

# Initialize colorama
init()

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        # Add color to the level name
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)

def setup_logging(name="lb_demo"):
    """Setup logging with colored console output and file logging"""
    # Get the directory where the script is located
    base_dir = Path(__file__).parent.parent.absolute()
    log_dir = base_dir / "lb_configs" / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # Create formatters
    colored_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create handlers
    file_handler = logging.FileHandler(log_dir / "demo.log")
    file_handler.setFormatter(file_formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)
    
    # Setup logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize the default logger
logger = setup_logging()

def cleanup():
    """Clean up all running processes and temporary files"""
    try:
        logger.info("🧹 Starting cleanup process...")
        # Kill Nginx and HAProxy processes
        for process in ["nginx", "haproxy"]:
            try:
                subprocess.run(["pkill", process], capture_output=True)
                logger.info(f"✅ Killed {process} processes")
            except Exception as e:
                logger.warning(f"⚠️ Error killing {process}: {str(e)}")

        # Clean up log files
        base_dir = Path(__file__).parent.parent.absolute()
        log_dir = base_dir / "lb_configs" / "logs"
        if log_dir.exists():
            logger.info("🗑️ Cleaning up log files...")
            for file in log_dir.glob("*"):
                try:
                    file.unlink()
                    logger.debug(f"✅ Removed {file}")
                except Exception as e:
                    logger.warning(f"⚠️ Error removing {file}: {str(e)}")
            logger.info("✨ Log files cleanup completed")

        logger.info("✅ Cleanup process completed successfully")

    except Exception as e:
        logger.error(f"❌ Error during cleanup: {str(e)}")

atexit.register(cleanup)