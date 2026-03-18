"""
Tests for PairingService — permanent, deterministic pairing codes using base32.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from services.sync.pairing_service import PairingInfo, PairingService


@pytest.fixture
def service():
    return PairingService()


MEMBER_TAG = "alice.laptop"
DEVICE_ID = "AAAAAAA-BBBBBBB-CCCCCCC-DDDDDDD-EEEEEEE-FFFFFFF-GGGGGGG-HHHHHHH"


class TestGenerateCode:
    def test_returns_string(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        assert isinstance(code, str)

    def test_code_contains_dashes(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        assert "-" in code

    def test_code_is_uppercase(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        # All non-dash chars should be uppercase alphanumeric
        for part in code.split("-"):
            assert part == part.upper()

    def test_code_blocks_are_1_to_4_chars(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        for part in code.split("-"):
            assert 1 <= len(part) <= 4

    def test_deterministic_same_input(self, service):
        code1 = service.generate_code(MEMBER_TAG, DEVICE_ID)
        code2 = service.generate_code(MEMBER_TAG, DEVICE_ID)
        assert code1 == code2

    def test_different_member_tag_different_code(self, service):
        code1 = service.generate_code("alice.laptop", DEVICE_ID)
        code2 = service.generate_code("bob.desktop", DEVICE_ID)
        assert code1 != code2

    def test_different_device_id_different_code(self, service):
        device2 = "ZZZZZZZ-YYYYYYY-XXXXXXX-WWWWWWW-VVVVVVV-UUUUUUU-TTTTTTT-SSSSSSS"
        code1 = service.generate_code(MEMBER_TAG, DEVICE_ID)
        code2 = service.generate_code(MEMBER_TAG, device2)
        assert code1 != code2

    def test_code_matches_expected_format(self, service):
        """Code should look like KXRM-4HPQ-ANVY (groups of 4 separated by dashes)."""
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        parts = code.split("-")
        assert len(parts) >= 2  # At least 2 groups
        for part in parts:
            assert 1 <= len(part) <= 4
            assert part.isalnum()


class TestValidateCode:
    def test_roundtrip_member_tag(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        info = service.validate_code(code)
        assert info.member_tag == MEMBER_TAG

    def test_roundtrip_device_id(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        info = service.validate_code(code)
        assert info.device_id == DEVICE_ID

    def test_returns_pairing_info_model(self, service):
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        info = service.validate_code(code)
        assert isinstance(info, PairingInfo)

    def test_invalid_code_raises_value_error(self, service):
        with pytest.raises(ValueError):
            service.validate_code("INVALID-CODE-HERE")

    def test_empty_code_raises_value_error(self, service):
        with pytest.raises(ValueError):
            service.validate_code("")

    def test_case_insensitive_validation(self, service):
        """Codes should decode successfully in lowercase too."""
        code = service.generate_code(MEMBER_TAG, DEVICE_ID)
        info = service.validate_code(code.lower())
        assert info.member_tag == MEMBER_TAG
        assert info.device_id == DEVICE_ID

    def test_different_members_roundtrip(self, service):
        members = [
            ("alice.laptop", "AAAAAAA-BBBBBBB-CCCCCCC-DDDDDDD-EEEEEEE-FFFFFFF-GGGGGGG-HHHHHHH"),
            ("bob.desktop", "ZZZZZZZ-YYYYYYY-XXXXXXX-WWWWWWW-VVVVVVV-UUUUUUU-TTTTTTT-SSSSSSS"),
            ("carol.server", "1111111-2222222-3333333-4444444-5555555-6666666-7777777-8888888"),
        ]
        for member_tag, device_id in members:
            code = service.generate_code(member_tag, device_id)
            info = service.validate_code(code)
            assert info.member_tag == member_tag
            assert info.device_id == device_id


class TestPairingInfo:
    def test_is_pydantic_model(self):
        info = PairingInfo(member_tag="alice.laptop", device_id="DEV-123")
        assert info.member_tag == "alice.laptop"
        assert info.device_id == "DEV-123"

    def test_immutable(self):
        info = PairingInfo(member_tag="alice.laptop", device_id="DEV-123")
        with pytest.raises(Exception):
            info.member_tag = "modified"
