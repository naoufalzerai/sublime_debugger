from __future__ import annotations

from ..import core
from ..import ui

from ..debugger import dap
from ..views.input_list_view import InputListView

from ..import commands
from ..import settings

from .import util


def is_valid_asset(asset: str):
	arch = core.platform.architecture
	if core.platform.windows and arch == 'x64':
		return asset.endswith('-x86_64-windows.vsix')
	elif core.platform.osx and arch == 'x64':
		return asset.endswith('-x86_64-darwin.vsix')
	elif core.platform.osx and arch == 'arm64':
		return asset.endswith('-aarch64-darwin.vsix')
	elif core.platform.linux and arch == 'x64':
		return asset.endswith('-x86_64-linux.vsix')
	elif core.platform.linux and arch == 'arm64':
		return asset.endswith('-aarch64-linux.vsix')
	else:
		raise core.Error('Your platforms architecture is not supported by vscode lldb. See https://github.com/vadimcn/vscode-lldb/releases/latest')

class LLDB(dap.AdapterConfiguration):

	type = 'lldb'
	docs = 'https://github.com/vadimcn/vscode-lldb/blob/master/MANUAL.md#starting-a-new-debug-session'

	installer = util.GitInstaller (
		type='lldb',
		repo='vadimcn/vscode-lldb', 
		is_valid_asset=is_valid_asset
	)

	lldb_show_disassembly = settings.Setting[str](
		key='lldb_show_disassembly',
		default='auto',
		visible=False,
	)
	lldb_display_format = settings.Setting[str](
		key='lldb_display_format',
		default='auto',
		visible=False,
	)
	lldb_dereference_pointers = settings.Setting[bool](
		key='lldb_dereference_pointers',
		default=True,
		visible=False,
	)

	lldb_library = settings.Setting['str|None'](
		key='lldb_library',
		default=None,
		description='Which lldb library to use'
	)

	def __init__(self) -> None:
		commands.Command(
			name='LLDB Toggle Disassembly',
			key='lldb_toggle_disassembly',
			action=lambda debugger: self.toggle_disassembly(debugger)
		)
		commands.Command(
			name='LLDB Display Options',
			key='lldb_display',
			action=lambda debugger: self.display_menu(debugger).run()
		)
		commands.Command(
			name='LLDB Toggle Dereference',
			key='lldb_toggle_dereference',
			action=lambda debugger: self.toggle_deref(debugger)
		)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		install_path = self.installer.install_path()
		port = util.get_open_port()
		command = [
			f'{install_path}/extension/adapter/codelldb',
			f'--port',
			f'{port}',
		]

		liblldb = LLDB.lldb_library
		if liblldb:
			command.extend(['--liblldb', liblldb])

		return await dap.SocketTransport.connect_with_process(log, command, port)

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'custom':
			configuration.request = 'launch'
			configuration['request'] = 'launch'
			configuration['custom'] = True

		configuration['_adapterSettings'] = self.adapter_settings()

		if 'pid' in configuration and configuration['pid'] == '${command_pick_process}':
			from ..util import select_process
			configuration['pid'] = await select_process()

		return configuration


	def adapter_settings(self):
		return {
			'showDisassembly': self.lldb_show_disassembly,
			'displayFormat': self.lldb_display_format,
			'dereferencePointers': self.lldb_dereference_pointers,
		}
		# showDisassembly: 'auto', #'always' | 'auto' | 'never' = 'auto';
		# displayFormat: 'auto', # 'auto' | 'hex' | 'decimal' | 'binary' = 'auto';
		# dereferencePointers: True
		# evaluationTimeout: number;
		# suppressMissingSourceFiles: boolean;
		# consoleMode: 'commands' | 'expressions';
		# sourceLanguages: string[];
		# terminalPromptClear: string[];

	# lldb settings must be resent to the debugger when updated
	# we only resend them when chaging through the ui if not the adapter needs to be restarted

	@core.run
	async def updated_settings(self, debugger: dap.Debugger) -> None:
		for session in debugger.sessions:
			if session.adapter_configuration.type == LLDB.type:
				await session.request('_adapterSettings', self.adapter_settings())


	def toggle_disassembly(self,debugger: dap.Debugger):
		print('toggle_disassembly')
		if self.lldb_show_disassembly == 'auto':
			self.lldb_show_disassembly = 'always'
		else:
			self.lldb_show_disassembly = 'auto'

		self.updated_settings(debugger)


	def toggle_deref(self, debugger: dap.Debugger):
		self.lldb_dereference_pointers = not self.lldb_dereference_pointers
		self.updated_settings(debugger)


	def display_menu(self,debugger: dap.Debugger):
		def set_display(mode: str):
			self.lldb_display_format = mode
			self.updated_settings(debugger)

		return ui.InputList('Display Options') [
			ui.InputListItemChecked(lambda: set_display('auto'), self.lldb_display_format == 'auto', 'Auto', 'Auto'),
			ui.InputListItemChecked(lambda: set_display('hex'), self.lldb_display_format == 'hex', 'Hex', 'Hex'),
			ui.InputListItemChecked(lambda: set_display('decimal'), self.lldb_display_format == 'decimal', 'Decimal', 'Decimal'),
			ui.InputListItemChecked(lambda: set_display('binary'), self.lldb_display_format == 'binary', 'Binary', 'Binary'),
		]
			

	def ui(self, debugger: dap.Debugger):
		return InputListView(ui.InputList()[
			ui.InputListItemOnOff(lambda: self.toggle_disassembly(debugger), 'Disassembly', 'Disassembly', self.lldb_show_disassembly != 'auto'),
		])
