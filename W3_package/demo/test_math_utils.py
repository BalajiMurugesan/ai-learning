import pytest

def add_two_numbers(a,b):
    """Takes two numbers and returns their sum."""
    return a + b

def test_add_two_numbers_positive():
    """Test adding two positive numbers."""
    assert add_two_numbers(3, 5) == 8

def test_add_two_numbers_negative():
    """Test adding negative numbers."""
    assert add_two_numbers(-2, -4) == -6

def test_add_two_numbers_floats():
    """Test adding floating-point numbers."""
    assert add_two_numbers(2.5, 1.1) == 3.6