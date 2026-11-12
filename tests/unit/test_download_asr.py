import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import download_asr


class DownloadAsrTests(unittest.TestCase):
    def test_http_download_keeps_default_progress_and_verifies_required_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'whisper'
            def snapshot(**options):
                self.assertEqual(os.environ['HF_HUB_DISABLE_XET'],'1')
                for name in ['config.json','model.bin','tokenizer.json','vocabulary.txt']:
                    (folder/name).write_bytes(b'content')
            with patch.dict(os.environ,{},clear=False),patch('huggingface_hub.snapshot_download',side_effect=snapshot) as call:
                download_asr.download(folder)
            options=call.call_args.kwargs
            self.assertEqual(options['repo_id'],'Systran/faster-whisper-small')
            self.assertEqual(options['max_workers'],1)
            self.assertNotIn('local_dir_use_symlinks',options)
            self.assertNotIn('tqdm_class',options)
            self.assertNotIn('token',options)

    def test_incomplete_download_is_not_reported_as_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ,{},clear=False),patch('huggingface_hub.snapshot_download'):
                with self.assertRaisesRegex(RuntimeError,'config.json'):
                    download_asr.download(temp)
