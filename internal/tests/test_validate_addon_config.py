"""Regression checks for Supervisor mappings and nested default-option coverage."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("addon_config_validator", ROOT / "internal/validate-addon-config.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ManifestValidationTests(unittest.TestCase):
    def test_supported_mapping_forms_preserve_paths(self):
        self.assertEqual(validator.validate_maps([
            {"type": "homeassistant_config", "path": "/config", "read_only": False},
            {"type": "app_config", "path": "/addon_config", "read_only": False},
            {"type": "all_app_configs", "path": "/addon_configs", "read_only": True},
            {"type": "local_apps", "path": "/addons", "read_only": False},
            "share:rw", "media:ro", "backup", "data",
        ]), [])

    def test_invalid_mapping_entries(self):
        for entries in ["share:rw", [123], [{}], [{"type": "wrong"}], ["share:write"], ["share:rw:ro"],
                        [{"type": "share", "read_only": "false"}], [{"type": "share", "path": ""}],
                        [{"type": "share", "path": "/"}], [{"type": "share", "path": "relative"}],
                        [{"type": "share", "path": "/x/../share"}]]:
            with self.subTest(entries=entries):
                self.assertTrue(validator.validate_maps(entries))

    def test_legacy_types_and_conflicts(self):
        for old, new in validator.LEGACY_MAP_TYPES.items():
            with self.subTest(old=old):
                self.assertIn("deprecated", " ".join(validator.validate_maps([old])))
                self.assertIn("incompatible", " ".join(validator.validate_maps([old, new])))
        self.assertIn("incompatible", " ".join(validator.validate_maps(["config:rw", "addon_config:rw"])))

    def test_duplicate_effective_destinations_and_types(self):
        for entries in [["share:rw", "share:ro"],
                        ["share", {"type": "media", "path": "/share/"}],
                        ["app_config", {"type": "homeassistant_config", "path": "/config"}]]:
            self.assertIn("duplicate", " ".join(validator.validate_maps(entries)))

    def test_nested_default_keys_and_lists_do_not_expose_values(self):
        errors = validator.validate_option_keys(
            {"sops": {"git_token": "private-value"}, "connections": [{"unknown": "private-value"}]},
            {"sops": {"file": "str"}, "connections": [{"name": "str"}]},
        )
        self.assertEqual(len(errors), 2)
        self.assertIn("options.sops.git_token", errors[0])
        self.assertIn("options.connections[0].unknown", errors[1])
        self.assertNotIn("private-value", " ".join(errors))
        self.assertEqual(validator.validate_option_keys({"arbitrary": {"deep": True}}, False), [])
        self.assertTrue(validator.validate_option_keys({"undeclared": True}, None))
        self.assertEqual(validator.validate_option_keys({"sops": {"git_token": ""}}, {"sops": {"git_token": "password?"}}), [])

    def test_secrets_sync_defaults_and_mount_contract(self):
        path = ROOT / "secrets-sync/config.yaml"
        manifest = yaml.safe_load(path.read_text())
        self.assertEqual(validator.validate_config(path), [])
        self.assertEqual({m["type"]: (m["path"], m["read_only"]) for m in manifest["map"]}, {
            "homeassistant_config": ("/config", False), "app_config": ("/addon_config", False),
            "all_app_configs": ("/addon_configs", True),
        })
        self.assertEqual(manifest["schema"]["sops"]["git_token"], "password?")
        self.assertEqual(manifest["schema"]["sops"]["source"], "list(file|git)?")
        old = {**manifest, "map": ["config:rw", "addon_config:rw", "all_addon_configs:ro"]}
        old["schema"] = {**manifest["schema"], "sops": {"file": "str", "flatten_separator": "str"}}
        with tempfile.TemporaryDirectory() as directory:
            old_path = Path(directory) / "config.yaml"
            old_path.write_text(yaml.safe_dump(old))
            errors = " ".join(validator.validate_config(old_path))
        self.assertIn("incompatible", errors)
        for key in ("source", "git_url", "git_branch", "git_path", "git_username", "git_token"):
            self.assertIn(f"options.sops.{key}", errors)

    def test_repository_manifests_are_valid(self):
        for path in sorted(ROOT.glob("*/config.yaml")):
            if (path.parent / "build.yaml").exists():
                with self.subTest(addon=path.parent.name):
                    self.assertEqual(validator.validate_config(path), [])


if __name__ == "__main__":
    unittest.main()
