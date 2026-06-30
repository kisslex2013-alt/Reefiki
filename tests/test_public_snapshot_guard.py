import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicSnapshotGuardTests(unittest.TestCase):
    def test_all_real_projects_are_classified_private_or_public(self):
        projects_root = ROOT / "projects"
        actual_projects = sorted(
            path.name for path in projects_root.iterdir() if path.is_dir() and path.name != "_template"
        )
        private_path = ROOT / "scripts" / "public-snapshot.private-projects.txt"
        public_path = ROOT / "scripts" / "public-snapshot.public-projects.txt"
        private_projects = sorted(
            line.strip()
            for line in private_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        public_projects = sorted(
            line.strip()
            for line in public_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        self.assertTrue(private_projects)
        self.assertEqual(["reefiki-demo"], public_projects)
        classified = set(private_projects) | set(public_projects)
        self.assertEqual([], [name for name in actual_projects if name not in classified])


if __name__ == "__main__":
    unittest.main()
