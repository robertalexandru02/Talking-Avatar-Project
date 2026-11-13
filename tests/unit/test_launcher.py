import io
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import start


class LauncherTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.env = self.root / 'backend/.venv'
        self.python = self.env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        self.python.parent.mkdir(parents=True)
        self.python.touch()
        self.requirements = self.root / 'backend/requirements.txt'
        self.requirements.write_text('fastapi\n')
        for name, value in [('ROOT',self.root), ('ENV',self.env), ('REQUIREMENTS',self.requirements)]:
            replacement = patch.object(start,name,value)
            replacement.start(); self.addCleanup(replacement.stop)

    def installed_whisper(self):
        folder = self.root / 'backend/models/whisper-small'
        folder.mkdir(parents=True)
        for name in ['config.json','model.bin','tokenizer.json','vocabulary.txt']:
            (folder/name).write_bytes(b'content')
        return folder

    def test_fresh_install_creates_environment_with_pip_before_installing(self):
        self.python.unlink()
        with patch.object(start.venv,'EnvBuilder') as builder,patch.object(start,'install_step') as run:
            builder.return_value.create.side_effect=lambda folder:self.python.touch()
            self.assertEqual(start.prepare_environment(),self.python)
        builder.assert_called_once_with(with_pip=True)
        builder.return_value.create.assert_called_once_with(self.env)
        self.assertEqual(run.call_args_list[0].args[0][-3:],['pip','setuptools','wheel'])
        self.assertIn('-r',run.call_args_list[1].args[0])

    def test_install_output_is_logged_and_failed_steps_are_reported(self):
        start.install_step([sys.executable,'-u','-c',"print('setup output')"])
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            start.install_step([sys.executable,'-u','-c',"import sys;print('failure detail',file=sys.stderr);sys.exit(3)"])
        self.assertEqual(failure.exception.returncode,3)
        log=(self.root/'artifacts/install.log').read_text(encoding='utf-8')
        self.assertIn('setup output',log)
        self.assertIn('failure detail',log)

    def test_warning_followed_by_silence_keeps_status_visible_until_success(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            start.install_step([sys.executable,'-u','-c',
                "import time;print('WARNING: old installer',flush=True);time.sleep(.15)"],
                label='Dependente',heartbeat_interval=.02)
        text=output.getvalue()
        self.assertIn('avertisment in jurnal',text)
        self.assertIn('proces activ',text)
        self.assertIn('[OK] Dependente',text)
        self.assertNotIn('%',text)
        self.assertNotIn('[EROARE]',text)

    def test_dependencies_install_once_and_refresh_after_requirements_change(self):
        with patch.object(start,'install_step') as run:
            start.prepare_environment();start.prepare_environment()
            self.assertEqual(run.call_count,2)
            self.requirements.write_text('fastapi\nhttpx\n')
            start.prepare_environment()
            self.assertEqual(run.call_count,4)

    def test_failed_dependency_install_is_retried(self):
        with patch.object(start,'install_step',side_effect=subprocess.CalledProcessError(1,'pip')):
            with self.assertRaises(subprocess.CalledProcessError):start.prepare_environment()
        self.assertFalse((self.env/'.requirements.sha256').exists())
        with patch.object(start,'install_step') as run:
            start.prepare_environment()
            self.assertEqual(run.call_count,2)

    def test_existing_models_do_not_trigger_model_downloads(self):
        self.installed_whisper()
        with patch.object(start,'run') as run, patch.object(start,'urlopen',side_effect=AssertionError('unexpected download')):
            start.prepare_models('http://localhost:11434','gemma3:4b',{'models':[{'name':'gemma3:4b'}]})
        self.assertEqual(run.call_count,1)  # Voice script skips files already present.
        self.assertIn('download_voices.py',str(run.call_args.args[0][-1]))

    def test_partial_whisper_install_is_completed(self):
        folder=self.installed_whisper();(folder/'tokenizer.json').write_bytes(b'')
        with patch.object(start,'run') as run:
            start.prepare_models('http://localhost:11434','gemma3:4b',{'models':[{'name':'gemma3:4b'}]})
        self.assertEqual(run.call_count,2)
        self.assertIn('download_asr.py',str(run.call_args.args[0][-1]))

    def test_interrupted_llm_download_does_not_continue_setup(self):
        response=io.BytesIO(b'{"status":"pulling","completed":50,"total":100}\n')
        with patch.object(start,'urlopen',return_value=response),patch.object(start,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'intrerupta'):
                start.prepare_models('http://localhost:11434','gemma3:4b',{'models':[]})
        run.assert_not_called()

    def test_missing_configured_model_is_pulled_successfully(self):
        self.installed_whisper()
        response=io.BytesIO(b'{"status":"success"}\n')
        with patch.object(start,'urlopen',return_value=response) as request,patch.object(start,'run'):
            start.prepare_models('http://localhost:11434','custom-model',{'models':[]})
        import json
        self.assertEqual(json.loads(request.call_args.args[0].data),{'model':'custom-model'})

    def test_existing_ollama_is_reused_without_owning_the_process(self):
        with patch.object(start,'get_json',return_value={'models':[]}),patch.object(start.subprocess,'Popen') as spawn:
            installed,owned=start.connect_ollama('http://localhost:11434')
        self.assertIsNone(owned)
        spawn.assert_not_called()

    def test_remote_configuration_does_not_start_a_local_service(self):
        with patch.object(start,'get_json',side_effect=OSError),patch.object(start.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'OLLAMA_URL'):
                start.connect_ollama('http://custom-server:11434')
        spawn.assert_not_called()
