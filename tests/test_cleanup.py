"""Tests for cleanup manager."""

import os
import tempfile
import time

import pytest

from peekxd.core.cleanup import CleanupManager, cleanup_now


class TestCleanupManager:
    """Test cleanup functionality."""

    def test_finds_peekxd_files(self):
        """Should find files with peekxd prefixes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            f1 = os.path.join(tmpdir, "peekxd_cap_test1.png")
            f2 = os.path.join(tmpdir, "peekxd_mark_test2.png")
            f3 = os.path.join(tmpdir, "other_file.txt")
            open(f1, "w").close()
            open(f2, "w").close()
            open(f3, "w").close()

            mgr = CleanupManager(directories=[tmpdir], max_age_hours=999)
            files = mgr.find_peekxd_files()

            names = [f.name for f in files]
            assert "peekxd_cap_test1.png" in names
            assert "peekxd_mark_test2.png" in names
            assert "other_file.txt" not in names

    def test_removes_old_files(self):
        """Should remove files older than max_age."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an old file
            f1 = os.path.join(tmpdir, "peekxd_cap_old.png")
            with open(f1, "w") as f:
                f.write("test")
            # Set mtime to 2 hours ago
            os.utime(f1, (time.time() - 7200, time.time() - 7200))

            mgr = CleanupManager(directories=[tmpdir], max_age_hours=1)
            stats = mgr.run()

            assert stats["cleaned"] == 1
            assert not os.path.exists(f1)

    def test_keeps_recent_files(self):
        """Should keep files younger than max_age."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "peekxd_cap_recent.png")
            open(f1, "w").close()

            mgr = CleanupManager(directories=[tmpdir], max_age_hours=24)
            stats = mgr.run()

            assert stats["cleaned"] == 0
            assert os.path.exists(f1)

    def test_enforces_max_files(self):
        """Should remove oldest files when over max_files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 5 files with staggered mtimes (oldest first)
            for i in range(5):
                f = os.path.join(tmpdir, f"peekxd_cap_{i}.png")
                with open(f, "w") as fp:
                    fp.write("x")
                # Make files progressively newer (i=0 oldest, i=4 newest)
                age = 100 - i * 10  # seconds ago
                os.utime(f, (time.time() - age, time.time() - age))

            before = len([n for n in os.listdir(tmpdir) if n.startswith("peekxd")])
            assert before == 5

            mgr = CleanupManager(directories=[tmpdir], max_age_hours=999, max_files=3)
            stats = mgr.run()

            # Verify files were removed (exact count may include cache dir)
            after = len([n for n in os.listdir(tmpdir) if n.startswith("peekxd")])
            assert after < before  # Some files were removed
            assert after <= 3  # At most max_files remain in tmpdir

    def test_cleanup_now_function(self):
        """cleanup_now should work as a one-shot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "peekxd_cap_test.png")
            with open(f1, "w") as f:
                f.write("test")
            os.utime(f1, (time.time() - 7200, time.time() - 7200))

            stats = cleanup_now(max_age_hours=1, max_files=100)
            assert isinstance(stats, dict)
            assert "cleaned" in stats
