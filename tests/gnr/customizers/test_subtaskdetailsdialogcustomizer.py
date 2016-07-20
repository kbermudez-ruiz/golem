from unittest import TestCase

from mock import Mock

from golem.task.taskstate import SubtaskState

from gnr.application import GNRGui
from gnr.customizers.subtaskdetailsdialogcustomizer import SubtaskDetailsDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.dialog import SubtaskDetailsDialog


class TestSubtaskDetailsDialogCustomizer(TestCase):
    def test_subtask_customizer(self):
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic = RenderingApplicationLogic()

        subtask_state = SubtaskState()
        subtask_details_dialog = SubtaskDetailsDialog(gnrgui.main_window.window)
        customizer = SubtaskDetailsDialogCustomizer(subtask_details_dialog, logic, subtask_state)
        assert isinstance(customizer, SubtaskDetailsDialogCustomizer)
        assert "0.000000 ETH" == "{}".format(customizer.gui.ui.priceLabel.text())
        subtask_state.value = 157.03 * 10 ** 16
        customizer.update_view(subtask_state)
        assert "1.570300 ETH" == "{}".format(customizer.gui.ui.priceLabel.text())

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()