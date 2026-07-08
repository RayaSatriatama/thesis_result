#!/usr/bin/env python
"""
Setup script untuk environment initialization.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check Python version compatibility."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")


def create_venv():
    """Create virtual environment if not exists."""
    venv_path = Path("venv")
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return

    print("📦 Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    print("✅ Virtual environment created")


def install_requirements():
    """Install dependencies dari requirements.txt."""
    print("📥 Installing dependencies...")

    # Determine pip executable
    if sys.platform == "win32":
        pip_exe = Path("venv/Scripts/pip.exe")
    else:
        pip_exe = Path("venv/bin/pip")

    if not pip_exe.exists():
        print("❌ Virtual environment not activated")
        sys.exit(1)

    # Upgrade pip
    subprocess.run([str(pip_exe), "install", "--upgrade", "pip"], check=True)

    # Install requirements
    subprocess.run([str(pip_exe), "install", "-r", "requirements.txt"], check=True)
    print("✅ Dependencies installed")


def setup_env_file():
    """Setup .env file dari .env.example."""
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if env_path.exists():
        print("✅ .env file already exists")
        return

    if not env_example_path.exists():
        print("❌ .env.example not found")
        return

    print("📝 Creating .env from .env.example...")
    with open(env_example_path, "r") as f_in:
        with open(env_path, "w") as f_out:
            f_out.write(f_in.read())

    print("✅ .env file created")
    print("⚠️  Please edit .env file dengan your API keys")


def create_directories():
    """Create necessary directories."""
    print("📁 Creating directory structure...")

    directories = [
        "data/raw/hanna_dataset",
        "data/raw/story_corpus",
        "data/processed/knowledge_graph",
        "data/processed/lightrag_storage",
        "data/results",
        "logs",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

    print("✅ Directory structure created")


def download_nltk_data():
    """Download required NLTK data."""
    print("📥 Downloading NLTK data...")
    try:
        import nltk

        nltk.download("punkt", quiet=True)
        nltk.download("stopwords", quiet=True)
        nltk.download("vader_lexicon", quiet=True)
        print("✅ NLTK data downloaded")
    except ImportError:
        print("⚠️  NLTK not installed, skipping...")


def main():
    """Main setup function."""
    print("\n" + "=" * 60)
    print("🚀 Setup Environment untuk Penelitian Skripsi")
    print("=" * 60 + "\n")

    check_python_version()
    create_venv()
    install_requirements()
    setup_env_file()
    create_directories()
    download_nltk_data()

    print("\n" + "=" * 60)
    print("✅ Setup completed successfully!")
    print("=" * 60)
    print("\n📌 Next steps:")
    print("1. Edit .env file dengan your API keys")
    print("2. Activate virtual environment:")
    if sys.platform == "win32":
        print("   .\\venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    print("3. Download HANNA dataset:")
    print("   python scripts/download_dataset.py")
    print("4. Build Knowledge Graph:")
    print("   python scripts/build_kg.py")
    print("5. Run experiment:")
    print("   python scripts/run_experiment.py")
    print()


if __name__ == "__main__":
    main()
