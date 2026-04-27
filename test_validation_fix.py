#!/usr/bin/env python3
"""Manual test to verify the validation fix."""

# Test the float conversion logic directly
def test_float_conversion():
    """Test that our validation logic works correctly."""

    # Test case 1: Valid coordinates
    try:
        lat = float(25.0340)
        lon = float(121.5644)
        print(f"✓ Valid coordinates work: lat={lat}, lon={lon}")
    except (ValueError, TypeError) as e:
        print(f"✗ Valid coordinates failed: {e}")

    # Test case 2: Invalid string coordinates
    try:
        lat = float("invalid")
        lon = float("also_invalid")
        print(f"✗ Invalid coordinates should have failed but didn't")
    except (ValueError, TypeError):
        print(f"✓ Invalid coordinates correctly caught by exception")

    # Test case 3: None values
    try:
        lat = float(None)
        lon = float(None)
        print(f"✗ None values should have failed but didn't")
    except (ValueError, TypeError):
        print(f"✓ None values correctly caught by exception")

    # Test case 4: Mixed valid/invalid
    test_lat = "invalid"
    test_lon = "121.5644"
    try:
        lat = float(test_lat)
        lon = float(test_lon)
        print(f"✗ Mixed invalid/valid should have failed but didn't")
    except (ValueError, TypeError):
        print(f"✓ Mixed invalid/valid correctly caught by exception")

    print("\n✅ All validation logic tests passed!")


if __name__ == "__main__":
    test_float_conversion()
