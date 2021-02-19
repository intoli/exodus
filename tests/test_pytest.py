# -*- coding: utf-8 -*-
import pytest


def test_catching_a_value_error():
    """Temporary test to make sure that we can run tests."""
    with pytest.raises(KeyError):
        {}['no-matching-key']
