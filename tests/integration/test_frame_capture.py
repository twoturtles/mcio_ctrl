"""Frame capture and image data tests."""

import numpy as np
import pytest

from .conftest import FRAME_SHAPE, IntegrationController


@pytest.mark.integration
def test_frame_dimensions(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    assert obs.frame_height == FRAME_SHAPE[0]
    assert obs.frame_width == FRAME_SHAPE[1]


@pytest.mark.integration
def test_frame_data_present(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    assert len(obs.frame) > 0


@pytest.mark.integration
def test_get_frame_shape(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    frame = obs.get_frame()
    assert frame.shape == FRAME_SHAPE
    assert frame.dtype == np.uint8


@pytest.mark.integration
def test_frame_not_black(ctrl: IntegrationController) -> None:
    obs = ctrl.send_and_recv()
    frame = obs.get_frame()
    assert frame.sum() > 0
