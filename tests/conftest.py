import sys
from pathlib import Path

# Add src/ directory to python path for imports
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

# Mock VLC in sys.modules to prevent load failures in headless or systems without VLC native libraries
import unittest.mock
mock_vlc = unittest.mock.MagicMock()
sys.modules['vlc'] = mock_vlc
sys.modules['python-vlc'] = mock_vlc
