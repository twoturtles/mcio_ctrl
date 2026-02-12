"""Frame capture and image data tests."""

import numpy as np
import pytest

from .conftest import ControllerHolder, send_and_recv


@pytest.mark.integration
def test_frame_dimensions(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    assert obs.frame_width == 854
    assert obs.frame_height == 480


@pytest.mark.integration
def test_frame_data_present(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    assert len(obs.frame) > 0


@pytest.mark.integration
def test_get_frame_shape(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    frame = obs.get_frame()
    assert frame.shape == (480, 854, 3)
    assert frame.dtype == np.uint8


@pytest.mark.integration
def test_frame_not_black(ctrl: ControllerHolder) -> None:
    obs = send_and_recv(ctrl)
    frame = obs.get_frame()
    assert frame.sum() > 0
