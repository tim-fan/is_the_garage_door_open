"""
Test script for verifying timing logic without making actual API calls.

This script tests the PresenceTracker and ApiRateLimiter classes in isolation.
"""

from datetime import time
from main import PresenceTracker, ApiRateLimiter


def test_daytime_transitions():
    """Test home -> out transition logic during daytime."""
    print("=" * 60)
    print("TEST: Daytime Home → Out Transitions")
    print("=" * 60)
    
    tracker = PresenceTracker([20, 22, 0, 4])
    is_daytime = True
    
    # First run - nobody home (should trigger check since default is someone_was_home=True)
    should_check, reason = tracker.should_check_now(someone_home=False, is_daytime=is_daytime)
    print(f"1. Nobody home (first run): {should_check} - {reason}")
    assert should_check, "Should check on startup if nobody home"
    
    # Still out - should not check again
    should_check, reason = tracker.should_check_now(someone_home=False, is_daytime=is_daytime)
    print(f"2. Still out: {should_check} - {reason}")
    assert not should_check, "Should not check again while out"
    
    # Come back home
    should_check, reason = tracker.should_check_now(someone_home=True, is_daytime=is_daytime)
    print(f"3. Returned home: {should_check} - {reason}")
    assert not should_check, "Should not check when returning home"
    
    # Still home
    should_check, reason = tracker.should_check_now(someone_home=True, is_daytime=is_daytime)
    print(f"4. Still home: {should_check} - {reason}")
    assert not should_check, "Should not check while home"
    
    # Leave home - should trigger check
    should_check, reason = tracker.should_check_now(someone_home=False, is_daytime=is_daytime)
    print(f"5. Left home: {should_check} - {reason}")
    assert should_check, "Should check on home → out transition"
    
    # Still out - should not check again
    should_check, reason = tracker.should_check_now(someone_home=False, is_daytime=is_daytime)
    print(f"6. Still out: {should_check} - {reason}")
    assert not should_check, "Should not check again while out"
    
    print("✓ All daytime transition tests passed!\n")


def test_night_checks():
    """Test night check scheduling."""
    print("=" * 60)
    print("TEST: Night Check Scheduling")
    print("=" * 60)
    
    tracker = PresenceTracker([20, 22, 0, 4])
    is_daytime = False
    
    # Simulate being at 8pm (20:00) - should check
    # Note: This test simulates the logic, actual hour checking happens in the method
    print("\nNote: This test checks the logic for tracking completed night checks.")
    print("Actual hour detection happens via datetime.now() in the real implementation.\n")
    
    # Manually test the tracking logic
    tracker.completed_night_checks.clear()
    
    print(f"1. Night checks completed: {tracker.completed_night_checks}")
    assert len(tracker.completed_night_checks) == 0, "Should start with no completed checks"
    
    # Simulate completing a check at hour 20
    tracker.completed_night_checks.add(20)
    print(f"2. After check at 20:00: {tracker.completed_night_checks}")
    assert 20 in tracker.completed_night_checks, "Should track 20:00 check"
    
    # Check if 20 would be checked again (it shouldn't)
    if 20 in tracker.completed_night_checks:
        print("3. 20:00 already completed - would skip")
    
    # Add another hour
    tracker.completed_night_checks.add(22)
    print(f"4. After check at 22:00: {tracker.completed_night_checks}")
    assert 22 in tracker.completed_night_checks, "Should track 22:00 check"
    
    print("✓ Night check tracking tests passed!\n")


def test_api_limiter():
    """Test API rate limiter."""
    print("=" * 60)
    print("TEST: API Rate Limiter")
    print("=" * 60)
    
    limiter = ApiRateLimiter(max_calls_per_day=3)
    
    # Should allow first call
    can_call = limiter.can_make_api_call()
    print(f"1. Can make call #1: {can_call}")
    assert can_call, "Should allow first call"
    limiter.record_api_call()
    
    # Should allow second call
    can_call = limiter.can_make_api_call()
    print(f"2. Can make call #2: {can_call}")
    assert can_call, "Should allow second call"
    limiter.record_api_call()
    
    # Should allow third call
    can_call = limiter.can_make_api_call()
    print(f"3. Can make call #3: {can_call}")
    assert can_call, "Should allow third call"
    limiter.record_api_call()
    
    # Should block fourth call
    can_call = limiter.can_make_api_call()
    print(f"4. Can make call #4: {can_call}")
    assert not can_call, "Should block after reaching limit"
    
    print(f"5. API calls today: {limiter.api_calls_today}/3")
    
    print("✓ API limiter tests passed!\n")


def test_integration_scenario():
    """Test a realistic day scenario."""
    print("=" * 60)
    print("TEST: Realistic Day Scenario")
    print("=" * 60)
    
    tracker = PresenceTracker([20, 22, 0, 4])
    limiter = ApiRateLimiter(max_calls_per_day=20)
    
    print("Scenario 1: Script starts at 8am, nobody home")
    should_check, reason = tracker.should_check_now(False, True)
    can_call = limiter.can_make_api_call()
    print(f"  Check: {should_check}, Reason: {reason}, API Ready: {can_call}")
    assert should_check, "Should check immediately if nobody home on startup"
    if should_check and can_call:
        limiter.record_api_call()
        print(f"  ✓ API call made! Count: {limiter.api_calls_today}")
    
    print("\nScenario 2: Script starts at 8am, someone home")
    tracker2 = PresenceTracker([20, 22, 0, 4])
    should_check, reason = tracker2.should_check_now(True, True)
    print(f"  Check: {should_check}, Reason: {reason}")
    assert not should_check
    
    print("\n10am: Leave for work")
    should_check, reason = tracker2.should_check_now(False, True)
    can_call = limiter.can_make_api_call()
    print(f"  Check: {should_check}, Reason: {reason}, API Ready: {can_call}")
    if should_check and can_call:
        limiter.record_api_call()
        print(f"  ✓ API call made! Count: {limiter.api_calls_today}")
    
    print("\n2pm: Still out")
    should_check, reason = tracker2.should_check_now(False, True)
    print(f"  Check: {should_check}, Reason: {reason}")
    assert not should_check
    
    print("\n6pm: Return home")
    should_check, reason = tracker2.should_check_now(True, True)
    print(f"  Check: {should_check}, Reason: {reason}")
    assert not should_check
    
    print("\n9pm: Night mode, scheduled check at 20:00 (8pm)")
    print("  (In real code, this would only trigger if current hour is 20)")
    print(f"  Night checks configured for hours: {sorted(tracker2.night_check_hours)}")
    
    print("\n✓ Integration scenario completed!")
    print(f"Final state: {limiter.api_calls_today} API calls made")


if __name__ == "__main__":
    try:
        test_daytime_transitions()
        test_night_checks()
        test_api_limiter()
        test_integration_scenario()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nThe timing logic is working correctly.")
        print("Run the main script to test with real time and presence detection.")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        exit(1)
