
import sublime
import re

from ..import core, ui, dap

from .debugger_session import DebuggerSession
from .debugger_project import DebuggerProject

from .variables import Variable, VariableComponent

# Provides support for showing debug information when an expression is hovered
# sends the hovered word to the debug adapter to evaluate and shows a popup with the result
# word seperates and a word match regex can optionally be defined in the configuration to allow support
# for treating things like $word keeping the $ as part of the word

class ViewHoverProvider(core.Disposables):
	def __init__(self, project: DebuggerProject, debugger: DebuggerSession) -> None:
		super().__init__()
		self.debugger = debugger
		self.project = project
		self += ui.view_text_hovered.add(self.on_view_text_hovered)

	def on_view_text_hovered(self, event) -> None:
		if not self.project.is_source_file(event.view):
			return

		if self.debugger.state == DebuggerSession.stopped:
			return

		core.run(self.on_hover(event))

	async def on_hover(self, event):
		if not self.debugger.adapter:
			return

		r = self.debugger.adapter_configuration.on_hover_provider(event.view, event.point)
		if not r:
			return
		word_string, region = r
		
		try:
			response = await self.debugger.adapter.Evaluate(word_string, self.debugger.callstack.selected_frame, 'hover')
			await core.sleep(0.25)
			variable = dap.Variable("", response.result, response.variablesReference)
			event.view.add_regions('selected_hover', [region], scope="comment", flags=sublime.DRAW_NO_OUTLINE)

			def on_close() -> None:
				event.view.erase_regions('selected_hover')

			component = VariableComponent(Variable(self.debugger, variable))
			component.toggle_expand()
			ui.Popup(component, event.view, region.a, on_close=on_close)

		# errors trying to evaluate a hover expression should be ignored
		except dap.Error as e:
			core.log_error("adapter failed hover evaluation", e)
